import pytest
import config
import urlvalidate
import hashlib
from butype import *
from butypes import *
from test_helpers import app, raw_file, member_list, proposal_vote, makeTestKey, makeTestAction, member_a, member_v

from io import BytesIO

prefix=config.web_prefix_internal

def find(client, url, contains=None, ct_like=None):
    res = client.get(url)
    assert res.status_code == 200
    if contains is not None:
        for x in res.response:
            if x.find(contains):
                break
        else:
            assert False
    if ct_like is not None:
        assert ct_like in dict(res.headers)["Content-Type"]
        
def dont_find(client, url):
    res = client.get(url)
    assert res.status_code == 404

def unauthorized(client, url):
    res = client.get(url)
    assert res.status_code == 401

def get_method_not_allowed(client, url):
    res = client.get(url)
    assert res.status_code == 405
    
        
def test_static(client, app):
    dont_find(client, "/")
    find(client, prefix)
    find(client, prefix+"js/bitcoinjs.js", b"feross")
    find(client, prefix+"unpublished-proposals", b"unpublished proposals")

    config.test_mode = False
    dont_find(client, prefix+"debug")
    dont_find(client, prefix+"debug/objects")
    dont_find(client, prefix+"debug/testkeys")
    dont_find(client, prefix+"debug/current-member-list-hash")
    dont_find(client, prefix+"debug/meta-for-raw-file/"+64*"0")
    dont_find(client, prefix+"debug/vote-for-raw-file/"+64*"0")
    dont_find(client, prefix+"debug/result-for-vote/"+64*"0")
    dont_find(client, prefix+"debug/summary-of-proposal-vote-result/"+64*"0")
    
    config.test_mode = True
    find(client, prefix+"debug")
    find(client, prefix+"debug/objects")
    find(client, prefix+"debug/testkeys")
    find(client, prefix+"debug/current-member-list-hash")

    # exercise serve.py some more ...
    dont_find(client, prefix+"debug/meta-for-raw-file/"+64*"0")
    dont_find(client, prefix+"debug/vote-for-raw-file/"+64*"0")
    dont_find(client, prefix+"debug/result-for-vote/"+64*"0")
    dont_find(client, prefix+"debug/summary-of-proposal-vote-result/"+64*"0")

    get_method_not_allowed(client, prefix+"action")
    
    
def test_render_raw(client, app, raw_file, proposal_vote):
    pvr = proposal_vote

    # unpublished raw file
    unauthorized(client, prefix+"render/raw_file/"+raw_file.hashref())
    unauthorized(client, prefix+"raw/raw_file/"+raw_file.hashref())

    raw_file.proposal_metadata.file_public=True
    dont_find(client, prefix+"render/raw_file/"+raw_file.hashref())
    find(client, prefix+"raw/raw_file/"+raw_file.hashref(), ct_like="application/pdf")
    
    find(client, prefix+"render/member/fce7de9a7ca1a81c80151f724c13fd89eece971276555abca7b0f13d813f7f04", ct_like="text/html")
    find(client, prefix+"raw/member/fce7de9a7ca1a81c80151f724c13fd89eece971276555abca7b0f13d813f7f04", ct_like="application/json") 
    
    dont_find(client, prefix+"render/member/"+64*"1")
    dont_find(client, prefix+"raw/member/"+64*"1")
    
    find(client, prefix+"render/proposal_vote/"+pvr.hashref())
    find(client, prefix+"raw/proposal_vote/"+pvr.hashref(), ct_like="application/json")
    
def test_form1(client, app):
    find(client, prefix+"form/generic/"+64*"1")
    dont_find(client, prefix+"form/invalid")
    
def test_form2(client, app):
    find(client, prefix+"form/cast-member-ballot/name/address")

def test_form3(client, app):
    find(client, prefix+"form/close-member-elections")

def test_action1(client, app, raw_file):
    data={}
    res = client.post(prefix+"action", data=data)
    assert res.status_code == 403

    # action_string missing
    data["author_name"]="member_a"
    res = client.post(prefix+"action", data=data)
    assert res.status_code == 403

    # sig missing
    data["action_string"]="dummy"
    res = client.post(prefix+"action", data=data)
    assert res.status_code == 403

    # invalid sig
    data["signature"]="dummysig"
    res = client.post(prefix+"action", data=data)
    assert res.status_code == 400

    # invalid author
    data["author_name"]="nonexist"
    res = client.post(prefix+"action", data=data)
    assert res.status_code == 403

    nm1addr=makeTestKey("newmember6")[1]
    newmember6 = Member("newmember6", nm1addr)

    ml = Global.current_member_list()
    
    action = makeTestAction(
        member_v(),
        "%s propose-member name %s address %s by member_v" % (
            ml.hashref(), newmember6.name, newmember6.address))

    
    # add upload
    data["upload"]=(BytesIO(b"dummy data"), "test.txt")
    data["author_name"]="member_v"
    data["action_string"] = action.action_string
    data["signature"] = action.signature
    res = client.post(prefix+"action", data=data)
    assert res.status_code == 400

    # add too-big upload
    data["upload"]=(BytesIO(b"x"*2000000), "test.txt")
    data["author_name"]="member_v"
    data["action_string"] = action.action_string
    data["signature"] = action.signature
    res = client.post(prefix+"action", data=data)
    assert res.status_code == 413

    # add upload that exists already
    data["upload"]=(BytesIO(b"test data"), "test.txt")
    data["author_name"]="member_v"
    data["action_string"] = action.action_string
    data["signature"] = action.signature
    res = client.post(prefix+"action", data=data)
    assert res.status_code == 409
    
    # finally, do everything right
    del data["upload"]
    res = client.post(prefix+"action", data=data)
    assert res.status_code == 201
    

def test_upload(client, app, raw_file):
    data={}
    res = client.post(prefix+"action", data=data)
    assert res.status_code == 403

    ml = Global.current_member_list()

    test_upload_data=b"Test upload data"
    upload_hash=hashlib.sha256(test_upload_data).hexdigest()
    
    action = makeTestAction(
        member_a(),
        "%s proposal-upload file %s by member_a" % (
            ml.hashref(), upload_hash))

    # upload missing
    data["author_name"]="member_a"
    data["action_string"] = action.action_string
    data["signature"] = action.signature
    res = client.post(prefix+"action", data=data)
    assert res.status_code == 400

    # upload of incorrect data
    data["upload"]=(BytesIO(test_upload_data+b" incorrect"), "test.txt")
    res = client.post(prefix+"action", data=data)
    assert res.status_code == 400
    
    # upload of correct data
    data["upload"]=(BytesIO(test_upload_data), "test.txt")
    res = client.post(prefix+"action", data=data)
    assert res.status_code == 201
    
    
def test_zip_download(client, app, member_list, raw_file, proposal_vote):
    with pytest.raises(urlvalidate.ValidationError):
        dont_find(client, prefix+"zip/invalid/invalid")
    with pytest.raises(urlvalidate.ValidationError):
        dont_find(client, prefix+"zip/invalid/"+"0"*64)
    with pytest.raises(urlvalidate.ValidationError):
        dont_find(client, prefix+"zip/raw_file/invalid")

    dont_find(client, prefix+"zip/raw_file/"+64*"0")

    res = client.get(prefix+"zip/member_list/"+member_list.hashref())
    assert res.status_code == 200

    unauthorized(client, prefix+"zip/raw_file/"+raw_file.hashref())

    raw_file.proposal_metadata.file_public=True 
    res = client.get(prefix+"zip/raw_file/"+raw_file.hashref())
    assert res.status_code == 200

    # FIXME: check all zip's contents!
    
    
    
    
    
