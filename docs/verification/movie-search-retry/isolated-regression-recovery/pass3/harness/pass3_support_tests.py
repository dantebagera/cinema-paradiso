import json,tempfile,unittest
from pathlib import Path
from pass3_support import new_fixture_root,verify_record
R=Path(__file__).parent
class HarnessContracts(unittest.TestCase):
    def test_repeat_runs_allocate_fresh_root_and_preserve_old_evidence(self):
        with tempfile.TemporaryDirectory(dir=R/'tmp') as temp:
            first=new_fixture_root(Path(temp),'probe');(first/'invalid-record.json').write_text('saved evidence')
            second=new_fixture_root(Path(temp),'probe')
            self.assertNotEqual(first,second)
            self.assertFalse((second/'invalid-record.json').exists())
            self.assertEqual((first/'invalid-record.json').read_text(),'saved evidence')
    def test_identity_requires_exact_child_root_nonce_and_nonproduction_port(self):
        good={'pid':123,'nonce':'private-nonce','root':str(R/'tmp/example'),'port':54321,'test_mode':True}
        self.assertEqual(verify_record(good,pid=123,nonce='private-nonce',root=R/'tmp/example'),good)
        for field,value in [('pid',456),('nonce','other'),('root',str(R/'checkout')),('port',5000),('port',8686),('port',0),('test_mode',False)]:
            with self.subTest(field=field,value=value):
                with self.assertRaises((AssertionError,ValueError)):
                    verify_record({**good,field:value},pid=123,nonce='private-nonce',root=R/'tmp/example')
        with self.assertRaises((AssertionError,ValueError)):
            verify_record({},pid=123,nonce='private-nonce',root=R/'tmp/example')
if __name__=='__main__':unittest.main()
