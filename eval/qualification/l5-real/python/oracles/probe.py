"""Evaluator-only independent behavioral oracle; stdlib test runner, no pytest."""
import argparse
import hashlib
import inspect
import json
import pathlib
import unittest
import numpy as np
from scipy import sparse
from sklearn import config_context, get_config
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import FeatureUnion, Pipeline
from sklearn.preprocessing import StandardScaler
import sklearn.utils._set_output as output_module
import sklearn.pipeline as pipeline_module
import sklearn.compose._column_transformer as compose_module


class Masker(TransformerMixin, BaseEstimator):
    def __init__(self, threshold=0):
        self.threshold = threshold

    def fit(self, X, y=None):
        self.n_features_in_ = np.asarray(X).shape[1]
        return self

    def transform(self, X):
        value = np.asarray(X, dtype=float)
        return np.ma.array(value, mask=value < self.threshold)

    def get_feature_names_out(self, input_features=None):
        return np.array(['x'+str(i) for i in range(self.n_features_in_)],dtype=object)


X = np.array([[-2., 3.], [4., -5.], [6., 7.]])


class Contract(unittest.TestCase):
    def assert_mask(self, actual, values, mask):
        self.assertIs(type(actual), np.ma.MaskedArray)
        np.testing.assert_array_equal(actual.data,values)
        np.testing.assert_array_equal(np.ma.getmaskarray(actual),mask)

    def test_transformer_dense_and_masked(self):
        scaler = StandardScaler().set_output(transform='masked')
        result = scaler.fit_transform(X)
        self.assertIs(type(result),np.ma.MaskedArray)
        np.testing.assert_allclose(result.data, StandardScaler().fit_transform(X))
        self.assertFalse(np.ma.getmaskarray(result).any())
        masker = Masker().set_output(transform='masked').fit(X)
        self.assert_mask(masker.transform(X),X,X<0)
        sparse_scaler=StandardScaler(with_mean=False).set_output(transform='masked').fit(X)
        with self.assertRaisesRegex(ValueError,'sparse matrix'):
            sparse_scaler.transform(sparse.csr_matrix(X))

    def test_feature_union_pipeline_and_context(self):
        pipeline = Pipeline([('branches',FeatureUnion([('negative',Masker(0)),('small',Masker(5))]))]).set_output(transform='masked')
        values=np.hstack([X,X]); mask=np.hstack([X<0,X<5])
        self.assert_mask(pipeline.fit_transform(X),values,mask)
        self.assert_mask(pipeline.transform(X),values,mask)
        before=get_config()['transform_output']
        with config_context(transform_output='masked'):
            union=FeatureUnion([('negative',Masker(0)),('small',Masker(5))])
            self.assert_mask(union.fit_transform(X),values,mask)
        self.assertEqual(get_config()['transform_output'],before)

    def test_column_transformer_pipeline_and_context(self):
        def make():
            return Pipeline([('columns',ColumnTransformer([('first',FeatureUnion([('negative',Masker(0)),('small',Masker(5))]),[0]),('second',Masker(5),[1])]))])
        values=np.column_stack([X[:,0],X[:,0],X[:,1]])
        mask=np.column_stack([X[:,0]<0,X[:,0]<5,X[:,1]<5])
        pipeline=make().set_output(transform='masked')
        self.assert_mask(pipeline.fit_transform(X),values,mask)
        self.assert_mask(pipeline.transform(X),values,mask)
        before=get_config()['transform_output']
        with config_context(transform_output='masked'):
            self.assert_mask(make().fit_transform(X),values,mask)
        self.assertEqual(get_config()['transform_output'],before)


class Regression(unittest.TestCase):
    def test_default_dense_and_context_restored(self):
        before=get_config()['transform_output']
        with config_context(transform_output='default'):
            pipeline=Pipeline([('columns',ColumnTransformer([('first',StandardScaler(),[0]),('second',StandardScaler(),[1])]))])
            self.assertIs(type(pipeline.fit_transform(X)),np.ndarray)
            np.testing.assert_allclose(pipeline.transform(X),StandardScaler().fit_transform(X))
            union=FeatureUnion([('one',StandardScaler()),('two',StandardScaler())])
            self.assertIs(type(union.fit_transform(X)),np.ndarray)
        self.assertEqual(get_config()['transform_output'],before)

    def test_sparse_rejection_and_invalid_mode(self):
        scaler=StandardScaler(with_mean=False).set_output(transform='pandas').fit(X)
        with self.assertRaisesRegex(ValueError,'sparse matrix'):
            scaler.transform(sparse.csr_matrix(X))
        invalid=StandardScaler().set_output(transform='unregistered').fit(X)
        with self.assertRaisesRegex(ValueError,'output config must be'):
            invalid.transform(X)


class Result(unittest.TextTestResult):
    def startTest(self,test):
        super().startTest(test)
        self.rows=getattr(self,'rows',[])
    def addSuccess(self,test):
        super().addSuccess(test);self.rows.append({'id':test.id(),'status':'passed'})
    def addFailure(self,test,err):
        super().addFailure(test,err);self.rows.append({'id':test.id(),'status':'failed','error':self._exc_info_to_string(err,test)})
    def addError(self,test,err):
        super().addError(test,err);self.rows.append({'id':test.id(),'status':'error','error':self._exc_info_to_string(err,test)})


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('phase',choices=['requirement','regression'])
    parser.add_argument('--report',required=True)
    args=parser.parse_args()
    # Resolve exact source origins before invoking any test. Wheels supply only
    # compiled extensions; these three Python modules must come from checkout.
    origins={}
    for module in [output_module,pipeline_module,compose_module]:
        path=pathlib.Path(inspect.getfile(module)).resolve()
        if not path.is_relative_to(pathlib.Path('/workspace/sklearn')):
            raise RuntimeError('tested Python module escaped pinned source checkout: '+str(path))
        origins[module.__name__]={'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(Contract if args.phase=='requirement' else Regression)
    result=unittest.TextTestRunner(verbosity=2,resultclass=Result).run(suite)
    pathlib.Path(args.report).write_text(json.dumps({'phase':args.phase,'tests_run':result.testsRun,'success':result.wasSuccessful(),'tests':result.rows,'module_origins':origins},indent=2)+'\n')
    raise SystemExit(0 if result.wasSuccessful() else 1)
