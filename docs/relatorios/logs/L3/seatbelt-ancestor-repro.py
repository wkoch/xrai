import json,sys,subprocess,tempfile,hashlib
from pathlib import Path
sys.path.insert(0, str(Path.cwd()/"crates/xrai-eval/harness"))
from adapters import sandbox
binary=str((Path.cwd()/"target/debug/incremental-probe").resolve())
rows=[]
with tempfile.TemporaryDirectory(prefix="xrai-anchor-seatbelt-") as tmp:
 root=Path(tmp).resolve(); workspace=root/"nested"/"workspace"; workspace.mkdir(parents=True)
 (workspace/"source.rs").write_text("pub fn visible() {}\n")
 hidden=root/"oracle"; hidden.write_text("PRIVATE-ORACLE")
 other=root/"other-arm"; other.mkdir(); (other/"secret").write_text("OTHER-ARM")
 (workspace/"external-link").symlink_to(hidden)
 for fixed in [False,True]:
  profile_dir=root/("fixed" if fixed else "original"); profile_dir.mkdir()
  command,_=sandbox([binary,"."],workspace,profile_dir)
  profile=Path(command[2]); ancestors=list(workspace.parents)
  grant="(allow file-read-data "+" ".join("(literal "+json.dumps(str(p))+")" for p in ancestors)+")"
  original=profile.read_text().replace(grant, "")
  root_literal='(allow file-read* (literal "/"))'
  if root_literal not in original:
   original+=root_literal
  profile.write_text(original+(grant if fixed else ""))
  result=subprocess.run(command,input=b"INDEX\n",cwd=workspace,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=10,env={"PATH":"/usr/bin:/bin","LANG":"C.UTF-8"})
  rows.append({"fixed":fixed,"probe_exit":result.returncode,"stdout":result.stdout.decode(),"stderr":result.stderr.decode(),"ancestors":list(map(str,ancestors)),"profile":profile.read_text(),"binary_sha256":hashlib.sha256(Path(binary).read_bytes()).hexdigest()})
  if fixed:
   for label,path in [("workspace",workspace/"source.rs"),("oracle",hidden),("other_arm",other/"secret"),("symlink",workspace/"external-link")]:
    r=subprocess.run([command[0],"-f",str(profile),"/bin/cat",str(path)],cwd=workspace,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=10)
    rows[-1].setdefault("sentinels",[]).append({"label":label,"exit_code":r.returncode,"stdout":r.stdout.decode(),"stderr":r.stderr.decode()})
   assert result.returncode==0 and b"END\t" in result.stdout
   assert rows[-1]["sentinels"][0]["exit_code"]==0
   assert all(r["exit_code"]!=0 and r["stdout"]=="" for r in rows[-1]["sentinels"][1:])
  else:
   assert result.returncode!=0 and b"Operation not permitted" in result.stderr
Path("docs/relatorios/logs/L3/seatbelt-ancestor-repro-final.json").write_text(json.dumps({"status":"PASS","rows":rows},indent=2)+"\n")
print("literal ancestors A/B + workspace positive + 3 external denial sentinels PASS")
