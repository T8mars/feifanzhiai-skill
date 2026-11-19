import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

RUNTIME = Path(__file__).resolve().parents[1]/'scripts/runtime'
sys.path.insert(0,str(RUNTIME))
import chenyu_workflow as c


def schema():
    fields = [('node_138_value','string',True),('node_326_value','int',True),
              ('node_342_video','video_input',True),('node_386_image','image_input',True),
              ('node_387_image','image_input',False)]
    return {'workflow_id':c.WORKFLOW,'revision_id':'offline','may_incur_external_model_cost':False,
            'editable_parameter_manifest':[{'name':n,'value_type':t,'required':r} for n,t,r in fields],
            'candidate_output_manifest':[{'name':'render','type':'video'}]}


class ChenyuWorkflow(unittest.TestCase):
    def test_route_checks_required_fields_and_output(self):
        self.assertEqual(c.route(schema(),2),'render')
        s=schema()
        s['editable_parameter_manifest'].append({'name':'new','required':True})
        with self.assertRaises(ValueError):c.route(s,1)
        s=schema()
        s['candidate_output_manifest'] *= 2
        with self.assertRaises(ValueError):c.route(s,1)

    def test_external_cost_terms_are_checked_before_upload(self):
        s=schema()
        s['may_incur_external_model_cost']=True
        with self.assertRaises(ValueError):c.route(s,1)

    def setUp(self):
        tmp=tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name)
        for directory in ['补齐生成用','替换用参考图','提示词']:
            (self.root/directory).mkdir()
        (self.root/'补齐生成用/补齐后帧数.txt').write_text('004.mp4 56 二号\n015.mp4 73 一号二号',encoding='utf8')
        for n,ref in [('004','<Picture 1>'),('015','<Picture 1> and <Picture 2>')]:
            (self.root/'提示词'/(n+'.txt')).write_text(ref, encoding='utf8')
        c.save(self.root/'provider.json',{'provider':'chenyu','workflow_id':c.WORKFLOW,'api_key_file':'unused'})

    def test_second_source_role_alone_is_first_picture(self):
        self.assertEqual(c.inputs_for(self.root,'004')[2],[self.root/'替换用参考图/二号.png'])
        self.assertEqual([p.name for p in c.inputs_for(self.root,'015')[2]],['一号.png','二号.png'])
        with self.assertRaises(ValueError):c.inputs_for(self.root,'all')

    def test_restarting_uncertain_order_retains_key_and_never_posts_after_acceptance(self):
        for p in [self.root/'补齐生成用/015 73.mp4',self.root/'替换用参考图/一号.png',self.root/'替换用参考图/二号.png']:
            p.write_bytes(b'input')
        payloads=[]
        def call(path,body=None):
            if 'market/info' in path:return schema()
            if path.endswith('/submit'):
                payloads.append(body)
                if len(payloads)==1:raise TimeoutError('simulated lost receipt')
                return {'run_order_id':'order'}
            return {'run_order_id':'order','revision_id':'offline','run_status':'failed',
                    'error_code':'fixture','settlement_status':'released','final_amount':'0'}
        with patch.object(c,'Api') as client:
            client.return_value.call.side_effect=call
            client.return_value.upload.return_value='asset://fixture'
            with self.assertRaises(TimeoutError):c.run(self.root,'015')
            for _ in range(2):
                with self.assertRaises(RuntimeError):c.run(self.root,'015')
        self.assertEqual(len(payloads),2)
        self.assertEqual(payloads[0],payloads[1])
        self.assertEqual(set(payloads[0]['inputs']),{'node_386_image','node_387_image','node_342_video','node_138_value','node_326_value'})
        self.assertEqual(payloads[0]['inputs']['node_326_value'],73)
        self.assertEqual(client.return_value.upload.call_count,3)
