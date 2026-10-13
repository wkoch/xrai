"""Public composition of existing offline APIs; source callbacks are observations, not flags."""
import base64
import copy
from dataclasses import dataclass
import json
import math
from pathlib import Path
import threading
import time

from agent_ledger import canonical, sha
from execution_gate import EvidenceSnapshot, OfflineAuthorization, preflight
from execution_dispatch_v2 import DispatchSessionV2, FakeTransportV2, replay_dispatch_v2
from agent_adapter_protocol import (ScriptedAdapterProtocol, ToolSnapshot, replay_adapter,
    require, exact, decode, MAX_FRAME_BYTES, MAX_TRANSCRIPT_BYTES)

VERSION='xrai.eval.session-tool-guard.v1'
MAX_EVENTS=128
MAX_RECORD_BYTES=16*1024*1024
ROOT=Path(__file__).resolve().parents[3]
SOURCE_PATHS=tuple('crates/xrai-eval/harness/'+name for name in (
    'session_tool_guard.py','execution_gate.py','execution_dispatch_v2.py',
    'agent_adapter_protocol.py','lexical_retrieval.py','agent_ledger.py','offline_measurement.py','runner.py'))


def source_bindings():
    return {path:sha((ROOT/path).read_bytes()) for path in SOURCE_PATHS}


def finite(value):
    return type(value) in (int,float) and math.isfinite(value) and value>=0


def snapshot_record(snapshot):
    return {'manifest':snapshot.manifest,'evidence':{name:base64.b64encode(raw).decode() for name,raw in snapshot.evidence}}


def restore_snapshot(value):
    require(type(value) is dict and set(value)=={'manifest','evidence'} and type(value['evidence']) is dict,'owned gate snapshot fields')
    return EvidenceSnapshot.capture(value['manifest'],{name:base64.b64decode(raw,validate=True) for name,raw in value['evidence'].items()})


def authorization_record(value):
    require(type(value) is OfflineAuthorization,'actual typed offline allowance callback')
    result={name:getattr(value,name) for name in ('snapshot_sha256','budget_micro_usd','expires_monotonic','revoked')}
    require(type(result['snapshot_sha256']) is str and type(result['budget_micro_usd']) is int and result['budget_micro_usd']>=0 and finite(result['expires_monotonic']) and type(result['revoked']) is bool,'typed bounded offline allowance')
    return result


def prefix(raw):
    require(type(raw) is bytes and len(raw)<=MAX_TRANSCRIPT_BYTES,'bounded delegate transcript')
    return {'bytes':len(raw),'sha256':sha(raw)}


def refusal(header,observation):
    require(type(observation) is dict and set(observation)=={'gate','tool','allowance','source_bindings','callback_error','time','session'},'check observation fields')
    require(finite(observation['time']),'same finite guard/session clock')
    ledger=observation['session'];replay_dispatch_v2(ledger)
    require(exact(ledger['snapshot'],header['snapshot']) and exact(ledger['bindings'],header['bindings']) and
        exact(ledger['authorization'],header['session_authorization']),'guard/D01 immutable binding')
    if observation['callback_error'] is not None:
        require(type(observation['callback_error']) is str and 0<len(observation['callback_error'].encode())<=256 and
            observation['gate'] is None and observation['tool'] is None and observation['allowance'] is None and observation['source_bindings'] is None,'bounded failed capture; no readiness data')
        return 'callback_capture_failed'
    gate=restore_snapshot(observation['gate']);expected=restore_snapshot(header['snapshot'])
    try:expected.assert_current(gate.manifest,dict(gate.evidence))
    except ValueError:return 'gate_snapshot_changed'
    auth=observation['allowance']
    require(type(auth) is dict and set(auth)==set(header['allowance']) and type(auth['revoked']) is bool and
        type(auth['budget_micro_usd']) is int and auth['budget_micro_usd']>=0 and finite(auth['expires_monotonic']),'typed actual allowance observation')
    if not exact({k:v for k,v in auth.items() if k!='revoked'}, {k:v for k,v in header['allowance'].items() if k!='revoked'}):return 'allowance_binding_changed'
    if auth['revoked'] or ledger['revoked']:return 'authorization_revoked'
    if observation['time']>=auth['expires_monotonic']:return 'authorization_expired'
    if ledger['invalidated'] is not None:return 'session_invalidated'
    if ledger['budget_incidents'] or ledger['accounting']['budget_limit_respected'] is not True:return 'budget_incident'
    tool=ToolSnapshot.restore(observation['tool'])
    if tool.fingerprint!=ToolSnapshot.restore(header['tool_snapshot']).fingerprint:return 'tool_snapshot_changed'
    if not exact(observation['source_bindings'],header['source_bindings']):return 'method_source_changed'
    return None


@dataclass(frozen=True)
class ToolGuardBarriers:
    """Test-only events after delegated success/error, before public acceptance recheck."""
    after_delegate_reached: threading.Event|None=None
    after_delegate_release: threading.Event|None=None
    def pause(self):
        if self.after_delegate_reached is not None:self.after_delegate_reached.set()
        if self.after_delegate_release is not None:require(self.after_delegate_release.wait(10),'owned guard barrier timeout')


class GuardRefused(ValueError):pass


class SessionToolGuard:
    """Factory-owned public consumer; no original-session private method/attribute access."""
    def __init__(self,session,delegate,snapshot,tool_snapshot,*,current_manifest,current_evidence,
                 current_authorization,current_sources,current_producer,clock,barriers):
        require(type(session) is DispatchSessionV2 and type(delegate) is ScriptedAdapterProtocol and
            type(snapshot) is EvidenceSnapshot and type(tool_snapshot) is ToolSnapshot,'factory typed components')
        require(delegate.session is session and delegate.snapshot.fingerprint==tool_snapshot.fingerprint,'factory components share session/tool ownership')
        self._session,self._delegate,self.snapshot,self.tool_snapshot=session,delegate,snapshot,tool_snapshot
        self.current_manifest,self.current_evidence=current_manifest,current_evidence
        self.current_authorization,self.current_sources,self.current_producer=current_authorization,current_sources,current_producer
        require(all(callable(callback) for callback in (current_manifest,current_evidence,current_authorization,current_sources,current_producer,clock)),'actual byte/allowance callbacks, not ready flags')
        require(type(barriers) is ToolGuardBarriers,'typed deterministic guard barriers')
        self.clock,self.barriers=clock,barriers
        self._lock=threading.RLock();self.events=[];self.active={};self.seen=set();self.terminal=False
        ledger=session.record()
        self.header={'schema_version':VERSION,'snapshot':snapshot_record(snapshot),'tool_snapshot':tool_snapshot.as_dict(),
            'allowance':authorization_record(current_authorization()),'session_authorization':ledger['authorization'],
            'bindings':ledger['bindings'],'source_bindings':source_bindings(),'execution_kind':'guarded_scripted_retrieval',
            'provider_usage':None,'provider_charge':None,'model_tokens':None,'agent_run':False,'campaign_scoring_enabled':False}
        require(self.header['allowance']['revoked'] is False and exact({k:v for k,v in self.header['allowance'].items() if k!='revoked'}, {k:v for k,v in ledger['authorization'].items() if k!='scope'}),'initial exact unrevoked session allowance')
        require(len(canonical(self.header))<=MAX_FRAME_BYTES//2,'bounded initial guard capture; separate blobs not implemented')
        initial=self.check()
        require(initial['accepted'],'initial guard admission refused: '+str(initial['reason']))

    def _append(self,kind,details):
        event={'schema_version':VERSION,'sequence':len(self.events),'kind':kind,'details':copy.deepcopy(details),
            'previous_event_sha256':sha(canonical(self.events[-1])) if self.events else None}
        require(len(self.events)<MAX_EVENTS and len(canonical(event))+1<=MAX_FRAME_BYTES,'guard event/frame bound')
        require(sum(len(canonical(row))+1 for row in self.events)+len(canonical(event))+1<=MAX_TRANSCRIPT_BYTES,'guard journal byte ceiling')
        self.events.append(event)

    def _capture(self):
        # All caller I/O is outside the guard transition lock. Values become owned bytes.
        result={'gate':None,'tool':None,'allowance':None,'source_bindings':None,'callback_error':None}
        try:
            manifest=self.current_manifest();evidence=self.current_evidence()
            gate=EvidenceSnapshot.capture(manifest,evidence)
            tool=ToolSnapshot.capture(self._delegate.handler,self.current_sources(),self.current_producer())
            result.update(gate=snapshot_record(gate),tool=tool.as_dict(),allowance=authorization_record(self.current_authorization()),source_bindings=source_bindings())
            require(len(canonical(result))<=MAX_FRAME_BYTES//2,'owned current capture bound')
        except Exception as error:
            # An unavailable observation is a refusal, never a success inferred from flags.
            result={'gate':None,'tool':None,'allowance':None,'source_bindings':None,
                    'callback_error':(type(error).__name__+': '+str(error)).encode()[:256].decode('utf-8',errors='ignore')}
        return result

    def _check_locked(self,capture,operation_id,stage):
        observation=copy.deepcopy(capture);observation.update(time=self.clock(),session=self._session.record())
        require(finite(observation['time']) and all(observation['time']>=row['details']['observation']['time'] for row in self.events if row['kind']=='check'),'guard monotonic clock moved backwards')
        reason=refusal(self.header,observation)
        self._append('check',{'operation_id':operation_id,'stage':stage,'observation':observation,'reason':reason,'accepted':reason is None})
        if reason=='authorization_revoked' and not observation['session']['revoked']:self._session.revoke()
        elif reason in {'gate_snapshot_changed','allowance_binding_changed','tool_snapshot_changed','method_source_changed','callback_capture_failed'} and observation['session']['invalidated'] is None:self._session.invalidate('session tool guard: '+reason)
        return reason

    def check(self):
        capture=self._capture()
        with self._lock:
            require(not self.terminal,'guard terminal')
            reason=self._check_locked(capture,None,'public')
            return {'accepted':reason is None,'reason':reason,'snapshot_sha256':self.snapshot.fingerprint,
                'paid_provider_enabled':False,'campaign_scoring_enabled':False}

    def _operation(self,operation_id,method,arguments,invoke):
        require(type(operation_id) is str and bool(operation_id) and len(operation_id.encode())<=256,'bounded explicit operation identity')
        capture=self._capture()
        with self._lock:
            require(not self.terminal and operation_id not in self.seen,'unique guard operation before terminal')
            require(method!='dispatch_fake' or not self.active,'dispatch cannot replace active tool identities')
            require(not any(row=='dispatch_fake' for row in self.active.values()),'no tool while fake dispatch active')
            require(len(self.events)+4<MAX_EVENTS and sum(len(canonical(row))+1 for row in self.events)<MAX_TRANSCRIPT_BYTES-3*MAX_FRAME_BYTES,'reserve bounded journal capacity before delegated I/O')
            self.seen.add(operation_id);self.active[operation_id]=method
            before=self._delegate.transcript()
            self._append('begin',{'operation_id':operation_id,'method':method,'arguments':arguments,'delegate_prefix':prefix(before)})
            reason=self._check_locked(capture,operation_id,'before')
            if reason is not None:
                self._append('end',{'operation_id':operation_id,'accepted':False,'delegated':False,'delegate_error':None,
                    'reason':reason,'result':None,'delegate_prefix':prefix(self._delegate.transcript())})
                del self.active[operation_id]
                raise GuardRefused(reason)
        result=None;error=None
        try:
            result=invoke()
        except Exception as caught:error=(type(caught).__name__+': '+str(caught)).encode()[:256].decode('utf-8',errors='ignore')
        # No wrapper lock around handler/fake transport/barrier. Revoke/invalidate can progress.
        try:self.barriers.pause()
        except ValueError as caught:error=str(caught)
        capture=self._capture()
        with self._lock:
            reason=self._check_locked(capture,operation_id,'after')
            if error is not None and reason is None:reason='delegated_error'
            if method=='dispatch_fake' and error is None and not(result['committed'] and result['adapter_called']):reason=reason or 'dispatch_not_invoked'
            result_bytes=None if result is None else canonical(result)
            self._append('end',{'operation_id':operation_id,'accepted':reason is None,'delegated':True,
                'delegate_error':error,'reason':reason,'result':None if result_bytes is None else {'base64':base64.b64encode(result_bytes).decode(),'bytes':len(result_bytes),'sha256':sha(result_bytes)},
                'delegate_prefix':prefix(self._delegate.transcript())})
            del self.active[operation_id]
            if reason is not None:raise GuardRefused(reason)
            return copy.deepcopy(result)

    def dispatch_fake(self,attempt_id,call_id,request,maximum_micro_usd,*,retry_of=None):
        return self._operation('dispatch:'+attempt_id,'dispatch_fake',{'attempt_id':attempt_id,'call_id':call_id,'request':request,'maximum_micro_usd':maximum_micro_usd,'retry_of':retry_of},
            lambda:self._delegate.dispatch_fake(attempt_id,call_id,request,maximum_micro_usd,retry_of=retry_of))

    def recover(self,tool_call_id,query,*,method='bm25',top_k=5,max_wire_bytes=65536):
        arguments={'tool_call_id':tool_call_id,'query':query,'method':method,'top_k':top_k,'max_wire_bytes':max_wire_bytes}
        return self._operation('tool:'+tool_call_id,'recover',arguments,lambda:self._delegate.recover(**arguments))

    def expand(self,tool_call_id,snippet_ids,*,max_wire_bytes=65536):
        arguments={'tool_call_id':tool_call_id,'snippet_ids':snippet_ids,'max_wire_bytes':max_wire_bytes}
        return self._operation('tool:'+tool_call_id,'expand',arguments,lambda:self._delegate.expand(**arguments))

    def revoke(self):
        with self._lock:
            require(not self.terminal,'guard terminal');self._session.revoke()
            self._append('control',{'action':'revoke','reason':None,'session':self._session.record()})

    def invalidate(self,reason):
        require(type(reason) is str and 0<len(reason.encode())<=256,'bounded explicit invalidation')
        with self._lock:
            require(not self.terminal,'guard terminal');self._session.invalidate(reason)
            self._append('control',{'action':'invalidate','reason':reason,'session':self._session.record()})

    def reconcile_fake(self,attempt_id,**kwargs):
        with self._lock:
            require(not self.terminal,'late accounting before closing guard')
            changed=self._delegate.reconcile_fake(attempt_id,**kwargs)
            self._append('reconcile',{'attempt_id':attempt_id,'changed':changed,'session':self._session.record(),
                'delegate_prefix':prefix(self._delegate.transcript())})
            return changed

    def finish(self,state,answer=b''):
        capture=self._capture()
        with self._lock:
            require(not self.terminal and not self.active,'close once after all delegated I/O returns')
            reason=self._check_locked(capture,None,'final')
            if state=='completed' and reason is not None:raise GuardRefused(reason)
            require(state!='completed' or all(row['details']['accepted'] for row in self.events if row['kind']=='end'),'refused guard output cannot become completed')
            raw=self._delegate.finish(state,answer)
            self._append('final',{'state':state,'delegate_prefix':prefix(raw),'session':self._session.record()})
            self.terminal=True
        return self.record()

    def record(self):
        with self._lock:
            raw=self._delegate.transcript()
            result={'schema_version':VERSION,'header':copy.deepcopy(self.header),'events':copy.deepcopy(self.events),
                'delegate':{'base64':base64.b64encode(raw).decode(),'bytes':len(raw),'sha256':sha(raw)},
                'session':self._session.record(),'terminal':self.terminal}
            require(len(canonical(result))<=MAX_RECORD_BYTES,'complete guard record bound')
            return result


def make_guarded_fake_session(snapshot,authorization,handler,tool_snapshot,*,bindings,current_manifest,
    current_evidence,current_authorization,current_sources,current_producer,clock=time.monotonic,
    fake_transport=None,dispatch_barriers=None,guard_barriers=None):
    """One owner binds actual callbacks to both guard and D01, without patching either."""
    require(type(snapshot) is EvidenceSnapshot and type(authorization) is OfflineAuthorization,'owned typed gate/allowance')
    baseline=authorization_record(authorization);holder={}
    def allowance_for_dispatch():
        observed=authorization_record(current_authorization())
        if observed['revoked']:
            if 'session' in holder:holder['session'].revoke()
            raise ValueError('current offline allowance revoked')
        require(exact(observed,baseline),'current offline allowance binding changed')
    def manifest_for_dispatch():
        allowance_for_dispatch();return current_manifest()
    def evidence_for_dispatch():
        allowance_for_dispatch();return current_evidence()
    session=DispatchSessionV2(snapshot,preflight(snapshot),authorization,fake_transport or FakeTransportV2(),
        bindings=bindings,current_manifest=manifest_for_dispatch,current_evidence=evidence_for_dispatch,
        clock=clock,barriers=dispatch_barriers)
    holder['session']=session
    delegate=ScriptedAdapterProtocol(session,handler,tool_snapshot,current_sources=current_sources,
        current_producer=current_producer,clock=clock)
    return SessionToolGuard(session,delegate,snapshot,tool_snapshot,current_manifest=current_manifest,
        current_evidence=current_evidence,current_authorization=current_authorization,current_sources=current_sources,
        current_producer=current_producer,clock=clock,barriers=guard_barriers or ToolGuardBarriers())


def replay_guard(record):
    """Pure data: recompute public rechecks and correlate retained delegate output."""
    require(type(record) is dict and len(canonical(record))<=MAX_RECORD_BYTES and set(record)=={'schema_version','header','events','delegate','session','terminal'} and record['schema_version']==VERSION and record['terminal'] is True,'bounded closed guard record')
    # Decode once to reject nonfinite JSON numbers even nested in observations.
    json.loads(canonical(record),parse_constant=lambda _:(_ for _ in ()).throw(ValueError('nonfinite guard JSON')))
    header=record['header']
    require(type(header) is dict and set(header)=={'schema_version','snapshot','tool_snapshot','allowance','session_authorization','bindings','source_bindings','execution_kind','provider_usage','provider_charge','model_tokens','agent_run','campaign_scoring_enabled'} and header['schema_version']==VERSION,'guard header exact profile')
    require(header['execution_kind']=='guarded_scripted_retrieval' and header['agent_run'] is False and header['campaign_scoring_enabled'] is False and all(header[k] is None for k in ('provider_usage','provider_charge','model_tokens')),'guard fake/unknown profile')
    gate=restore_snapshot(header['snapshot']);decision=preflight(gate)
    require(decision.accepted and decision.intent=='smoke_seed','guard seed preflight')
    tool=ToolSnapshot.restore(header['tool_snapshot'])
    auth=header['allowance'];require(type(auth) is dict and set(auth)=={'snapshot_sha256','budget_micro_usd','expires_monotonic','revoked'} and auth['revoked'] is False and type(auth['budget_micro_usd']) is int and auth['budget_micro_usd']>=0 and finite(auth['expires_monotonic']) and auth['snapshot_sha256']==gate.fingerprint,'guard authorization capture')
    require(exact({k:v for k,v in auth.items() if k!='revoked'},{k:v for k,v in header['session_authorization'].items() if k!='scope'}),'guard allowance/session binding')
    require(type(header['source_bindings']) is dict and set(header['source_bindings'])==set(SOURCE_PATHS),'guard method source closure')
    require(exact(header['source_bindings'],source_bindings()),'guard proof method source changed')
    wrapped=record['delegate'];require(type(wrapped) is dict and set(wrapped)=={'base64','bytes','sha256'},'delegate wrapper fields')
    raw=base64.b64decode(wrapped['base64'],validate=True)
    require(type(wrapped['bytes']) is int and wrapped['bytes']==len(raw)<=MAX_TRANSCRIPT_BYTES and wrapped['sha256']==sha(raw),'retained delegate full bytes/hash')
    delegate_result=replay_adapter(raw);frames=raw.splitlines(keepends=True);delegated=[decode(frame) for frame in frames]
    require(exact(delegated[0]['details']['tool_snapshot'],header['tool_snapshot']),'same actual guarded tool capture')
    ledger=record['session'];replay_dispatch_v2(ledger)
    require(exact(ledger['snapshot'],header['snapshot']) and exact(ledger['bindings'],header['bindings']) and exact(ledger['authorization'],header['session_authorization']),'guard final session metadata')
    require(exact(next(e['details']['d01_record'] for e in reversed(delegated) if e['kind']=='ledger_snapshot'),ledger),'delegate final accounting retained intact')
    def checked_prefix(value):
        require(type(value) is dict and set(value)=={'bytes','sha256'} and type(value['bytes']) is int and 0<=value['bytes']<=len(raw),'typed delegate prefix')
        data=raw[:value['bytes']]
        require(not data or data.endswith(b'\n'),'prefix ends at complete delegate frame')
        require(sha(data)==value['sha256'],'delegate prefix audit retention')
        return [decode(frame) for frame in data.splitlines()]
    events=record['events'];require(type(events) is list and 1<=len(events)<=MAX_EVENTS and sum(len(canonical(e))+1 for e in events)<=MAX_TRANSCRIPT_BYTES,'guard journal bounds')
    active={};seen=set();prior=None;closed=False;accepted_tools=0;refused=0;retained=0;final_check=None
    shapes={'begin':{'operation_id','method','arguments','delegate_prefix'},'check':{'operation_id','stage','observation','reason','accepted'},
        'end':{'operation_id','accepted','delegated','delegate_error','reason','result','delegate_prefix'},
        'control':{'action','reason','session'},'reconcile':{'attempt_id','changed','session','delegate_prefix'},'final':{'state','delegate_prefix','session'}}
    def checked_ledger(value):
        nonlocal prior
        replay_dispatch_v2(value)
        require(exact(value['snapshot'],header['snapshot']) and exact(value['authorization'],header['session_authorization']) and exact(value['bindings'],header['bindings']),'guard intermediate immutable D01 metadata')
        require(prior is None or exact(value['events'][:len(prior['events'])],prior['events']),'guard D01 history cannot be replaced')
        require(exact(ledger['events'][:len(value['events'])],value['events']),'guard observation belongs to final D01 journal')
        prior=value
    for sequence,event in enumerate(events):
        require(type(event) is dict and set(event)=={'schema_version','sequence','kind','details','previous_event_sha256'} and event['schema_version']==VERSION and type(event['sequence']) is int and event['sequence']==sequence and event['previous_event_sha256']==(sha(canonical(events[sequence-1])) if sequence else None) and len(canonical(event))+1<=MAX_FRAME_BYTES,'typed bounded guard event/hash chain')
        kind,detail=event['kind'],event['details'];require(kind in shapes and type(detail) is dict and set(detail)==shapes[kind] and not closed,'exact guard event details/order')
        if kind=='begin':
            name,method=detail['operation_id'],detail['method']
            require(type(name) is str and 0<len(name.encode())<=256 and name not in seen and method in ('dispatch_fake','recover','expand'),'unique typed guard operation')
            require(method!='dispatch_fake' or not active,'dispatch cannot overwrite active tools')
            require(not any(row['method']=='dispatch_fake' for row in active.values()),'no tool before dispatch completes')
            require(type(detail['arguments']) is dict,'typed operation arguments');checked_prefix(detail['delegate_prefix'])
            seen.add(name);active[name]={'method':method,'arguments':detail['arguments'],'before':None,'after':None,'prefix':detail['delegate_prefix']}
        elif kind=='check':
            name=detail['operation_id'];require(type(detail['accepted']) is bool and detail['stage'] in ('public','before','after','final'),'typed public check')
            require(all(detail['observation']['time']>=old['details']['observation']['time'] for old in events[:sequence] if old['kind']=='check'),'guard check clock order')
            expected=refusal(header,detail['observation']);checked_ledger(detail['observation']['session'])
            require(detail['reason']==expected and detail['accepted'] is (expected is None),'guard decision derived from actual observation')
            if name is None:
                require(detail['stage'] in ('public','final'),'standalone check stage')
                if detail['stage']=='final':final_check=detail
            else:
                require(name in active and detail['stage'] in ('before','after'),'check active operation')
                row=active[name];require(row[detail['stage']] is None and (detail['stage']=='before' or row['before']['accepted'] is True),'one before/after check')
                row[detail['stage']]=detail
        elif kind=='end':
            name=detail['operation_id'];require(name in active and type(detail['accepted']) is bool and type(detail['delegated']) is bool,'typed one guard outcome')
            row=active.pop(name);require(row['before'] is not None,'operation requires precheck')
            prefix_events=checked_prefix(detail['delegate_prefix'])
            if not row['before']['accepted']:
                require(not detail['delegated'] and row['after'] is None and detail['result'] is None and detail['delegate_error'] is None and detail['reason']==row['before']['reason'] and not detail['accepted'],'before refusal invokes no delegate')
                require(detail['delegate_prefix']['bytes']>=row['prefix']['bytes'],'delegate prefix cannot roll back')
                if row['method']=='dispatch_fake':
                    require(not any(e['kind']=='dispatch' and e['identity']['attempt_id']==row['arguments']['attempt_id'] for e in prefix_events),'pre-refused dispatch cannot be delegated')
                else:
                    require(not any(e['kind']=='tool_request' and e['details']['tool_call_id']==row['arguments']['tool_call_id'] for e in prefix_events),'pre-refused tool cannot be delegated')
            else:
                require(detail['delegated'] and row['after'] is not None,'invoked operation requires postcheck')
                error=detail['delegate_error'];require(error is None or (type(error) is str and 0<len(error.encode())<=256),'bounded explicit delegated failure')
                result=None
                if detail['result'] is not None:
                    encoded=detail['result'];require(type(encoded) is dict and set(encoded)=={'base64','bytes','sha256'},'guard result retained bytes')
                    data=base64.b64decode(encoded['base64'],validate=True)
                    require(type(encoded['bytes']) is int and encoded['bytes']==len(data)<=MAX_FRAME_BYTES and encoded['sha256']==sha(data),'guard result hash/types/bound')
                    result=decode(data);require(canonical(result)==data,'canonical captured delegated result')
                reason=row['after']['reason'] or ('delegated_error' if error is not None else None)
                arguments=row['arguments']
                if row['method']=='dispatch_fake':
                    require(set(arguments)=={'attempt_id','call_id','request','maximum_micro_usd','retry_of'} and name=='dispatch:'+arguments['attempt_id'],'dispatch operation identity')
                    if result is not None:
                        matching=[e for e in prefix_events if e['kind']=='dispatch' and e['identity']['attempt_id']==arguments['attempt_id'] and e['identity']['call_id']==arguments['call_id']]
                        require(len(matching)==1 and exact(matching[0]['details']['outcome'],result),'dispatch result belongs to retained delegated outcome')
                        reserve=next(e for e in ledger['events'] if e['kind']=='reserve' and e['attempt_id']==arguments['attempt_id'])
                        require(exact(reserve['details'],{'call_id':arguments['call_id'],'request':arguments['request'],'maximum':arguments['maximum_micro_usd'],'retry_of':arguments['retry_of']}),'guard reserve/request/retry metadata')
                        if not(result['committed'] and result['adapter_called']):reason=reason or 'dispatch_not_invoked'
                else:
                    fields={'tool_call_id','query','method','top_k','max_wire_bytes'} if row['method']=='recover' else {'tool_call_id','snippet_ids','max_wire_bytes'}
                    require(set(arguments)==fields and name=='tool:'+arguments['tool_call_id'],'typed tool operation identity')
                    if result is not None:
                        request=[e for e in prefix_events if e['kind']=='tool_request' and e['details']['tool_call_id']==arguments['tool_call_id']]
                        response=[e for e in prefix_events if e['kind']=='tool_result' and e['details']['tool_call_id']==arguments['tool_call_id']]
                        require(len(request)==len(response)==1 and request[0]['details']['tool']==row['method'] and exact(request[0]['details']['arguments'],{k:v for k,v in arguments.items() if k!='tool_call_id'}) and base64.b64decode(response[0]['details']['wire_base64'],validate=True)==canonical(result),'guard tool result preserves paired delegate evidence')
                        if not detail['accepted']:retained+=1
                    if detail['accepted']:accepted_tools+=1
                require(detail['reason']==reason and detail['accepted'] is (reason is None) and (not detail['accepted'] or result is not None),'accepted guard output requires both checks and actual result')
            if not detail['accepted']:refused+=1
        elif kind=='control':
            require(detail['action'] in ('revoke','invalidate'),'public control operation')
            checked_ledger(detail['session'])
            if detail['action']=='revoke':require(detail['reason'] is None and detail['session']['revoked'] is True,'actual revocation retained')
            else:require(type(detail['reason']) is str and detail['session']['invalidated']==detail['reason'],'actual public invalidation retained')
        elif kind=='reconcile':
            require(type(detail['attempt_id']) is str and detail['attempt_id'] in detail['session']['attempts'] and type(detail['changed']) is bool,'typed late fake accounting')
            require(prior is not None and detail['changed'] is (not exact(prior['events'],detail['session']['events'])),'late reconciliation changed/idempotent observation')
            checked_ledger(detail['session']);checked_prefix(detail['delegate_prefix'])
        else:
            require(not active and final_check is not None and detail['state'] in ('completed','timeout','error','partial','cancelled') and exact(detail['delegate_prefix'],prefix(raw)),'closed guard state/full delegate bytes')
            require(detail['state']==delegated[-1]['details']['state'],'same explicit terminal state')
            require(detail['state']!='completed' or (final_check['accepted'] and refused==0),'refusal cannot be converted to completed')
            checked_ledger(detail['session']);require(exact(detail['session'],ledger),'final guard ledger');closed=True
    require(closed and not active,'complete guarded journal')
    return {'schema_version':'xrai.eval.session-tool-guard-replay.v1','verified':True,
        'accepted_tool_results':accepted_tools,'refused_operations':refused,'retained_but_not_returned_tool_results':retained,
        'delegate_tool_calls':delegate_result['tool_calls'],'virtual_accounting':ledger['accounting'],
        'agent_run':False,'paid_provider_enabled':False,'campaign_scoring_enabled':False,
        'provider_usage':None,'provider_charge':None,'model_tokens':None,'external_calls':0,
        'limits':['Callback checkpoints cannot detect external ABA between observations.','Delegate evidence is retained; only guard journal acceptance determines whether a result was returned.']}


def load_guard(raw):
    """Bounded data-only JSON decoder for the new standalone artifacts."""
    require(type(raw) is bytes and 0<len(raw)<=MAX_RECORD_BYTES,'guard input byte bound')
    def pairs(values):
        result={}
        for key,value in values:
            require(key not in result,'duplicate guard JSON key');result[key]=value
        return result
    def number(value):
        parsed=float(value);require(math.isfinite(parsed),'nonfinite guard number');return parsed
    try:
        value=json.loads(raw,object_pairs_hook=pairs,parse_float=number,
            parse_constant=lambda _:(_ for _ in ()).throw(ValueError('nonfinite guard number')))
    except RecursionError as error:raise ValueError('guard JSON nesting bound') from error
    require(raw==canonical(value)+b'\n','complete canonical guard artifact')
    return value
