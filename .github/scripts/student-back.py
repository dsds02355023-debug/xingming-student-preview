import json
import os
import subprocess
import time
from urllib.request import urlopen
from websocket import create_connection

PKG = os.environ['STUDENT_TEST_PACKAGE']

def adb(*args):
    return subprocess.check_output(['adb', *args], text=True).strip()

def wait(check, label):
    for _ in range(40):
        if check():
            return
        time.sleep(.25)
    raise AssertionError(label)

pid = adb('shell', 'pidof', PKG)
assert pid.isdigit(), pid
adb('forward', 'tcp:9222', 'localabstract:webview_devtools_remote_' + pid)
with urlopen('http://127.0.0.1:9222/json/list', timeout=10) as response:
    targets = json.load(response)
target = next(t for t in targets if t['type'] == 'page' and t['url'].endswith('/assets/index.html'))
ws = create_connection(target['webSocketDebuggerUrl'], timeout=10, suppress_origin=True)
seq = 0

def evaluate(expr):
    global seq
    seq += 1
    ws.send(json.dumps({'id': seq, 'method': 'Runtime.evaluate', 'params': {'expression': expr, 'returnByValue': True}}))
    while True:
        msg = json.loads(ws.recv())
        if msg.get('id') != seq:
            continue
        result = msg['result']
        assert 'exceptionDetails' not in result, result
        return result['result'].get('value')

visible = "id=>!!document.getElementById(id)?.getClientRects().length"
chart = "document.querySelector('[data-sw=chart]')"
wait(lambda: evaluate(f"document.readyState === 'complete' && !!{chart}?.getClientRects().length"), 'Workbench chart entry not visible')
evaluate(f'{chart}.click()')
wait(lambda: evaluate(f'({visible})("sur")'), 'Personal form not visible after opening chart')
assert evaluate('''(()=>{const s=document.getElementById('sur'),g=document.getElementById('giv');s.value='王';g.value='小明';document.getElementById('go').click();return true})()''')
wait(lambda: evaluate(f'({visible})("v2")'), 'Result did not open')
print('Result opened; sending Android KEYCODE_BACK', flush=True)
adb('shell', 'input', 'keyevent', 'KEYCODE_BACK')
wait(lambda: evaluate(f'({visible})("v1")&&!({visible})("v2")'), 'Back did not return to input form')
assert evaluate("document.getElementById('sur').value==='王' && document.getElementById('giv').value==='小明'"), 'Input was lost'
activities = adb('shell', 'dumpsys', 'activity', 'activities')
assert any(PKG + '/' in line for line in activities.splitlines() if 'ResumedActivity' in line), 'App left foreground'
print('PASS: Android Back returned to the form, preserved values and kept the app foreground')
ws.close()
