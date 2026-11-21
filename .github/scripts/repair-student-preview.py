#!/usr/bin/env python3
import hashlib
import re
from pathlib import Path

root = Path('smoke-source/app')
html = root / 'src/student/assets/index.html'
java = root / 'src/main/java/com/xingming/apps/MainActivity.java'
page = html.read_text(encoding='utf-8')
code = java.read_text(encoding='utf-8')
if 'student-preview-v142-repairs' in page or 'previewBackRepairV142' in code:
    raise SystemExit('Preview repairs already applied; refusing duplicate integration')

runtime = r'''
<script id="student-preview-v142-repairs">
(() => {
  const start = () => {
    const input = document.getElementById('v1');
    if (!input) throw new Error('Preview repair: input screen missing');
    const normalize = () => {
      input.querySelectorAll('details.fold8-compact-accordion details.fold8-compact-accordion').forEach(inner => {
        const outer = inner.parentElement?.closest('details.fold8-compact-accordion');
        if (outer && outer.contains(inner)) outer.replaceWith(inner);
      });
    };
    normalize();
    new MutationObserver(normalize).observe(input, {childList:true, subtree:true});
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start, {once:true});
  else start();
})();
</script>
'''
if page.lower().count('</body>') != 1:
    raise SystemExit('Unexpected HTML body structure')
page = page.replace('</body>', runtime + '</body>', 1)

old_guard = 'getPackageName().endsWith(".student")'
if old_guard not in code:
    raise SystemExit('Native student package guard missing; inspect MainActivity before changing Back')
code = code.replace(old_guard, '(getPackageName().endsWith(".student") || getPackageName().endsWith(".student.preview"))')
back_method = re.search(r'\bvoid\s+onBackPressed\s*\(', code)
if not back_method:
    raise SystemExit('Native onBackPressed method missing')
start = code.find('        web.evaluateJavascript("(()=>', back_method.start())
end = code.find('    private void defaultBack()', start)
if start < 0 or end < start:
    raise SystemExit('Native Back replacement anchors missing')
replacement = r'''        // previewBackRepairV142: preserve the page before delegating Home exit.
        web.evaluateJavascript("(()=>{"
            + "const vis=id=>{const e=document.getElementById(id);return !!(e&&!e.hidden&&e.getClientRects().length);};"
            + "const handled=()=>{window.__studentBackState='handled';window.__studentBackCount=(window.__studentBackCount||0)+1;return 'handled';};"
            + "if(vis('lx-image-save-modal')){const b=document.querySelector('#lx-image-save-modal [data-close]');if(b){b.click();return handled();}}"
            + "if(vis('lxSummaryCard')){const b=document.getElementById('lxOpen');if(b){b.click();return handled();}}"
            + "for(const [p,b] of [['lxSettingsPage','lxSettingsBack'],['v2','back'],['v3','bnback'],['v4','bhback'],['v1','swBack']]){"
            + "if(vis(p)){const btn=document.getElementById(b);if(btn){btn.click();return handled();}}}"
            + "const sw=document.getElementById('sw');if(vis('sw')&&sw.classList.contains('lxPage')){const b=document.getElementById('lxBack');if(b){b.click();return handled();}}"
            + "window.__studentBackState=vis('sw')?'home':'blocked';return window.__studentBackState;"
            + "})()", state -> {
            android.util.Log.d("StudentBack", "preview Back state=" + state);
            if (!isFinishing() && !isDestroyed() && "\"home\"".equals(state)) defaultBack();
        });
    }
    @Override public boolean dispatchKeyEvent(android.view.KeyEvent event) {
        if (event.getKeyCode() == android.view.KeyEvent.KEYCODE_BACK) {
            if (event.getAction() == android.view.KeyEvent.ACTION_UP) onBackPressed();
            return true;
        }
        return super.dispatchKeyEvent(event);
    }
'''
code = code[:start] + replacement + code[end:]
if len(re.findall(r'\bboolean\s+dispatchKeyEvent\s*\(', code)) != 1:
    raise SystemExit('Unexpected duplicate dispatchKeyEvent; refusing native build')
anchor = '        settings.setJavaScriptEnabled(true);'
if code.count(anchor) != 1:
    raise SystemExit('WebView initialization anchor missing')
code = code.replace(anchor, anchor + '''
        if (android.os.Build.VERSION.SDK_INT >= 33) {
            getOnBackInvokedDispatcher().registerOnBackInvokedCallback(
                android.window.OnBackInvokedDispatcher.PRIORITY_DEFAULT,
                () -> onBackPressed());
        }
''', 1)

scripts = Path('private-source/.github/scripts')
updates = {}
isolation = '''
# Preview CI isolation: never inherit a failed test's page, storage or display state.
for _command in (['am','force-stop',PKG], ['wm','density','160'], ['wm','size','1432x1080'], ['cmd','uimode','night','no'], ['pm','clear',PKG], ['am','start','-W','-n',PKG+'/com.xingming.apps.MainActivity']):
    _result = subprocess.run(['adb','shell',*_command], check=True, timeout=30, text=True, capture_output=True)
    print('TEST SETUP:', ' '.join(_command), _result.stdout.strip(), flush=True)
    if _command[:2] == ['pm','clear']:
        assert _result.stdout.strip() == 'Success', 'Test storage reset failed'
time.sleep(1)
'''
for name in ('student-settings-smoke.py','student-rules-smoke.py','student-home-back-smoke.py','student-result-layout-smoke.py'):
    p = scripts / name
    text = p.read_text(encoding='utf-8')
    pkg = "PKG = os.environ['STUDENT_TEST_PACKAGE']"
    if text.count(pkg) != 1:
        raise SystemExit('Test package anchor mismatch: ' + name)
    updates[p] = text.replace(pkg, pkg + '\n' + isolation, 1)

p = scripts / 'student-rules-smoke.py'
text = updates[p]
helper = '''
def assert_master_detail(label):
    layout = evaluate("""(()=>{const sw=document.getElementById('sw'),left=sw?.querySelector('.fold8-home-left'),body=document.getElementById('swBody'),back=document.getElementById('lxBack'),a=left?.getBoundingClientRect(),b=body?.getBoundingClientRect();return {page:!!sw?.classList.contains('lxPage'),grid:sw?getComputedStyle(sw).display:'',leftWidth:a?.width||0,bodyWidth:b?.width||0,leftRight:a?.right||0,bodyLeft:b?.left||0,bodyRight:b?.right||0,viewport:innerWidth,nav:!!left?.querySelector('nav [data-sw]'),backInLeft:!!left&&left.contains(back),backVisible:!!back&&!back.hidden&&!!back.getClientRects().length}})()""")
    print(label+' actual master-detail layout:',json.dumps(layout,ensure_ascii=False),flush=True)
    assert layout['page'] and layout['grid']=='grid' and layout['leftWidth']>0 and layout['bodyWidth']>350 and layout['bodyLeft']>=layout['leftRight']-1 and layout['bodyRight']<=layout['viewport']+2 and layout['nav'] and layout['backInLeft'] and layout['backVisible'], label+' actual master-detail layout failed: '+json.dumps(layout,ensure_ascii=False)
'''
a = text.index('wait("!!document.querySelector(\'#swBody .fold8-study-master-detail\')"')
b = text.index('\nevaluate("(()=>{const s=document.querySelector(\'#swBody .ruleSearch\')', a)
text = text[:a] + helper + "\nassert_master_detail('規則百科')\n" + text[b:]
old = "!!document.querySelector('#swBody .fold8-study-master-detail') &&"
if text.count(old) != 1:
    raise SystemExit('Rules subpage assertion anchor mismatch')
text = text.replace(old, "!!document.getElementById('swBody').getClientRects().length &&", 1)
a = text.index('    page_layout = evaluate(')
b = text.index('    evaluate("document.getElementById(\'lxBack\').click();true")', a)
text = text[:a] + '    assert_master_detail(page_title)\n' + text[b:]
updates[p] = text

p = scripts / 'student-result-layout-smoke.py'
text = updates[p]
old = "adb('shell', 'wm', 'size', '1432x1080')\nwait(\"innerWidth>=800 && innerWidth>innerHeight\""
new = "adb('shell', 'wm', 'size', '1432x1080')\nws.close()\nws = connect()\nSEQ = 0\nwait(\"innerWidth>=800 && innerWidth>innerHeight\""
if text.count(old) != 1:
    raise SystemExit('Result resize/reconnect anchor mismatch')
updates[p] = text.replace(old, new, 1)

p = scripts / 'student-home-back-smoke.py'
text = updates[p]
old = "    time.sleep(1)\n    back_state = evaluate("
new = """    time.sleep(1)
    _activities = adb('shell', 'dumpsys', 'activity', 'activities')
    assert any(PKG+'/' in line for line in _activities.splitlines() if 'ResumedActivity' in line), 'Hardware Back unexpectedly left the App foreground'
    ws.close()
    ws = connect_devtools()
    seq = 0
    back_state = evaluate("""
if text.count(old) != 1:
    raise SystemExit('Hardware Back diagnostic anchor mismatch')
updates[p] = text.replace(old, new, 1)

for p, text in updates.items():
    compile(text, str(p), 'exec')
java.write_text(code, encoding='utf-8')
html.write_text(page, encoding='utf-8')
for p, text in updates.items():
    p.write_text(text, encoding='utf-8')
Path('smoke-results').mkdir(exist_ok=True)
report = [str(p)+' '+hashlib.sha256(p.read_bytes()).hexdigest() for p in (java,html,*updates)]
Path('smoke-results/preview-repair-sha256.txt').write_text('\n'.join(report)+'\n', encoding='utf-8')
print('Applied generated preview UI/native repairs and isolated acceptance setup; test assertions retained or replaced with physical pane checks.')
