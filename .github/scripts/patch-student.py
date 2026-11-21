import sys
import re
from pathlib import Path

root = Path('smoke-source/app')

# 1. Update build.gradle
p_gradle = root / 'build.gradle'
s = p_gradle.read_text(encoding='utf-8')
assert s.count("applicationIdSuffix '.student'") == 1
p_gradle.write_text(s.replace("applicationIdSuffix '.student'", "applicationIdSuffix '.student.preview'").replace('姓名學・學生版', '姓名學・學生測試版'), encoding='utf-8')

# 2. Fix windowBackground in styles.xml
p_styles = root / 'src/main/res/values/styles.xml'
if p_styles.exists():
    st = p_styles.read_text(encoding='utf-8')
    if 'android:windowBackground' not in st:
        st = st.replace('</style>', '<item name="android:windowBackground">#F6F3FC</item></style>')
        p_styles.write_text(st, encoding='utf-8')

# 3. Fix FOUC (0.1s unstyled flash) in index.html by hoisting all template CSS into <head>
for p_html in root.rglob('index.html'):
    h = p_html.read_text(encoding='utf-8')
    
    # Extract late <style> blocks from bottom
    b_start = h.find('<style>', 640000)
    b_end = h.find('</body>')
    if b_start != -1 and b_end != -1:
        bottom_styles = []
        pos = b_start
        while pos != -1 and pos < b_end:
            s_end = h.find('</style>', pos)
            if s_end == -1: break
            s_end += len('</style>')
            bottom_styles.append(h[pos:s_end])
            pos = h.find('<style', s_end)
        hoisted_css = '\n'.join(bottom_styles)
        head_pos = h.find('</head>')
        if head_pos != -1:
            h = h[:head_pos] + hoisted_css + '\n' + h[head_pos:]

    # Unify root background
    old_bg = 'body{margin:0;color:var(--fg);font-family:"Noto Serif TC","PMingLiU","Songti TC",serif;line-height:1.6;background:#f8f3e3 linear-gradient(180deg,#f8f3e3 0%,#f8f3e3 45%,#e6f0e1 80%,#d3e7e5 100%) fixed;min-height:100vh}'
    if old_bg in h:
        new_bg = 'body{margin:0;color:var(--fg);font-family:system-ui,-apple-system,"Noto Sans TC",sans-serif;line-height:1.6;background:radial-gradient(ellipse at top left,#e4daf4 0,transparent 55%),#f6f3fa;min-height:100vh}'
        h = h.replace(old_bg, new_bg).replace('--bg:#f8f3e3;', '--bg:#f6f3fa;')
    p_html.write_text(h, encoding='utf-8')

# 4. Fix MainActivity.java
p_main = root / 'src/main/java/com/xingming/apps/MainActivity.java'
s = p_main.read_text(encoding='utf-8')
old = 'getPackageName().endsWith(".student")'
assert s.count(old) >= 2
s = s.replace(old, '(getPackageName().endsWith(".student") || getPackageName().endsWith(".student.preview"))')

start = s.index('        web.evaluateJavascript("(()=>')
end = s.index('    private void defaultBack()', start)
js_back = '''        web.evaluateJavascript("(()=>{"
            + "const vis=id=>{const e=document.getElementById(id);return !!(e&&!e.hidden&&e.getClientRects().length);};"
            + "for(const [p,b] of [['v2','back'],['v3','bnback'],['v4','bhback'],['v1','swBack']]) {"
            + "  if(vis(p)){const btn=document.getElementById(b);if(btn){btn.click();return 'handled';}}"
            + "}"
            + "return vis('sw')?'home':'blocked';"
            + "})()", state -> {
            if (!isFinishing() && !isDestroyed() && "\\"home\\"".equals(state)) defaultBack();
        });
    }
    @Override public boolean dispatchKeyEvent(android.view.KeyEvent event) {
        if (event.getKeyCode() == android.view.KeyEvent.KEYCODE_BACK) {
            if (event.getAction() == android.view.KeyEvent.ACTION_UP) {
                onBackPressed();
            }
            return true;
        }
        return super.dispatchKeyEvent(event);
    }
'''
s = s[:start] + js_back + s[end:]
p_main.write_text(s, encoding='utf-8')

for p in root.rglob('*.java'):
    s = p.read_text(encoding='utf-8')
    t = s.replace('"com.xingming.apps.student"', '"com.xingming.apps.student.preview"')
    if t != s:
        p.write_text(t, encoding='utf-8')

print("Successfully applied anti-flash and back fixes to smoke-source")
