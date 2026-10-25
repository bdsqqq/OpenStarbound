"""Synthetic verifier fixtures only: no runtime or physical BTree qualification."""
from copy import deepcopy
import hashlib
import unittest
import buffer_proof as p


def fixture(backend='rust'):
    def counts(modes):
        a=[int(i in modes and backend=='rust') for i in range(50)]
        return dict(attempt=a[:],success=a[:],exception=[0]*50)
    scopes=[dict(method=m,completed=True,calls=counts(p.ANCHORS.get(i,()))) for i,m in enumerate(p.METHODS)]
    total={k:[sum(s['calls'][k][i] for s in scopes) for i in range(50)] for k in ('attempt','success','exception')}
    events=[]
    rows=[[("begin",0,1,1,0),("incomplete-header",1,1,0,0),("before-trim",1,1,0,0),("after-trim",0,1,1,0)],
          [("begin",0,5,5,0),("incomplete-payload",2,5,3,0),("before-trim",2,5,3,0),("after-trim",0,5,5,0)],
          [("begin",0,14,14,0),("packet-complete",10,14,4,10),("incomplete-payload",12,14,2,10),("before-trim",12,14,2,10),("after-trim",0,4,4,10)],
          [("begin",0,10,10,0),("packet-complete",10,10,0,10),("before-trim",10,10,0,10),("after-trim",0,0,0,10)]]
    for stage,seq in enumerate(rows):
        events.append(dict(stage=stage,kind='receive',bytes=(1,4,9,6)[stage],cumulativeBytes=(1,5,14,20)[stage],bufferSize=(1,5,14,10)[stage]))
        events.extend(dict(stage=stage,kind=k,pos=a,size=b,remaining=c,consumed=d) for k,a,b,c,d in seq)
    pages=(b'BTreeDB5\x00\x00\x02\x00'+b'bufferlab'+bytes(7)+b'\x00\x00\x00\x20').ljust(512,b'\x00')
    pages=(pages+hashlib.sha256(b'buffer-payload').digest()+p.PAYLOAD[:208].encode()).ljust(2560,b'\x00').hex()
    return {'bufferProof':dict(version=1,backend=backend,nativeObservedCalls=13,scopes=scopes,calls=total,
        network=dict(transport='tcp',producer='independent-literal-raw-sender',inputEndpoint='127.0.0.1:40233',chosenPort=40233,
            ownedBindSucceeded=True,rulesVersion=5,streamEnabled=False,universeHandshake=False,expectedWireHex=p.WIRE,
            actualWireHex=p.WIRE,sentWireHex=p.WIRE,sendAttempts=4,stages=[dict(stage=i,sentBytes=t,receivedBytes=t,packetCount=c) for i,(t,c) in enumerate(zip((1,5,14,20),(0,0,1,2)))],
            parserEvents=events,acceptedPeerAddress='127.0.0.1',acceptedPeerPort=51515,acceptedPeerSource='OS-accept-sockaddr',
            clientLocalOsAvailable=False,receivedTexts=['BUF-A','BUF-B'],receivedPacketCount=2),
        save=dict(filename='/sandbox/buffer-save.sbvj',wireHex=p.SAVE_HEX,expectedWireHex=p.SAVE_HEX,value=deepcopy(p.VALUE),consumed=1594,atEnd=True),
        database=dict(filename='/sandbox/buffer-payload.btree',key='buffer-payload',blockSize=512,pagesHex=pages,foundHex=p.SAVE_HEX,
            memoryPagesHex=pages,memoryFoundHex=p.SAVE_HEX,memoryValue=deepcopy(p.VALUE),memoryConsumed=1594,memoryAtEnd=True,
            value=deepcopy(p.VALUE),consumed=1594,atEnd=True),
        visual=dict(imagePath=p.IMAGE,color=p.COLOR[:],sourceSize=[16,16],displaySize=[64,64],scale=4,label=p.LABEL))}


class BufferProofTests(unittest.TestCase):
    def test_native_and_rust_project_after_validation(self):
        self.assertEqual(p.validate(fixture('cpp')),p.validate(fixture()))

    def test_literals_frozen_before_capture(self):
        self.assertEqual(len(p.SAVE_BYTES),1594)
        self.assertEqual(p.SAVE_SHA256,'cc477d827fe5ea55b4afe7fa957c7660bbecfd30e2acf117ca9a0fc69d5d54a9')
        self.assertEqual(list(map(len,p.CHUNKS)),[1,4,9,6])

    def test_valid_extra_empty_poll_is_not_delivery_assumption(self):
        a=fixture();e=a['bufferProof']['network']['parserEvents']
        e[0:0]=[dict(stage=0,kind=k,pos=0,size=0,remaining=0,consumed=0) for k in ('begin','before-trim','after-trim')]
        a['bufferProof']['network'].update(chosenPort=40234,inputEndpoint='127.0.0.1:40234',acceptedPeerPort=51516,sendAttempts=5)
        self.assertEqual(p.validate(a),p.validate(fixture()))

    def test_corruptions_reject_before_projection(self):
        mutations=[lambda q:q['network'].update(actualWireHex='00'),
            lambda q:q['network'].update(expectedWireHex='00',actualWireHex='00',sentWireHex='00'),
            lambda q:q['network'].update(ownedBindSucceeded=False),
            lambda q:q['network'].update(acceptedPeerPort=True),
            lambda q:q['network'].update(acceptedPeerSource='cached-input'),
            lambda q:q['network'].update(receivedTexts=['BUF-B','BUF-A']),
            lambda q:q['network']['stages'][0].update(packetCount=1),
            lambda q:q['network']['parserEvents'][2].update(pos=0),
            lambda q:q['network']['parserEvents'][2].update(remaining=1),
            lambda q:q['network']['parserEvents'][2].update(pos=True),
            lambda q:q['network']['parserEvents'][0].update(cumulativeBytes=2),
            lambda q:q['network']['parserEvents'][0].update(bufferSize=2),
            lambda q:q['network']['parserEvents'].pop(2),
            lambda q:q['save'].update(wireHex='00',expectedWireHex='00'),
            lambda q:q['save'].update(atEnd=False),
            lambda q:q['database'].update(memoryFoundHex='00'),
            lambda q:q['database'].update(memoryAtEnd=False),
            lambda q:q['visual'].update(label='hardcoded'),
            lambda q:q['scopes'][0].update(method='fake decoder'),
            lambda q:q.update(nativeObservedCalls=0)]
        for i,mutate in enumerate(mutations):
            with self.subTest(i=i):
                value=fixture();mutate(value['bufferProof'])
                with self.assertRaises(ValueError):p.validate(value)

    def test_balanced_route_suppression_rejects(self):
        value=fixture();q=value['bufferProof']
        for key in ('attempt','success'):q['scopes'][0]['calls'][key][49]=0
        with self.assertRaisesRegex(ValueError,'source controller'):p.validate(value)

    def test_direct_file_reader_cannot_invent_buffer(self):
        value=fixture();q=value['bufferProof']
        for key in ('attempt','success'):
            q['scopes'][5]['calls'][key][0]=1;q['calls'][key][0]+=1
        with self.assertRaisesRegex(ValueError,'direct File reader'):p.validate(value)

    def test_paired_page_poison_rejects(self):
        value=fixture();d=value['bufferProof']['database'];raw=bytearray.fromhex(d['pagesHex']);raw[67]=1
        d['pagesHex']=d['memoryPagesHex']=raw.hex()
        with self.assertRaisesRegex(ValueError,'padding'):p.validate(value)


if __name__=='__main__':unittest.main()
