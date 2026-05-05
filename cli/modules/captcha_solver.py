#!/usr/bin/env python3
"""
Captcha Solver Module — CUA-ONLY (cua-driver drag + AppleEvents JS)
====================================================================
WAS: Hardcoded window position (73,70) → funktionierte nur zufällig
WARUM: Window-Position ist dynamisch, abhängig von Launch-Methode
WO: /Users/jeremy/dev/stealth-runner/cli/modules/captcha_solver.py
WIE: list_windows → get window position, AX tree → get toolbar height,
     DOM coordinates + toolbar → window coordinates → cua-driver drag
WANN: 2026-05-05, GoCaptcha getestet, 5/5 erfolgreich
WOMIT: cua-driver (CGEvent drag), AppleEvents JS (DOM query + scrollIntoView)
ZWECK: Slide-Captcha und Drag-Drop-Captcha via reale MouseEvents lösen
"""
import subprocess, json, time, re

class CaptchaSolver:
    def __init__(self, pid, wid):
        self.pid = pid
        self.wid = wid
        self._wx, self._wy = 0, 0
        self._toolbar = 87
        self._refresh_offsets()
    
    def _refresh_offsets(self):
        # WICHTIG: Filter by BOTH pid AND window_id — ein PID kann mehrere Fenster haben.
        # Ohne window_id-Filter wurde das falsche Fenster (z.B. "Übersetzen"-Popup)
        # als Quelle für die Window-Position verwendet → Koordinaten um Hunderte Pixel falsch.
        # Bug entdeckt: 2026-05-05, Window war bei (100,50) aber Offset kam von (829,130).
        p = subprocess.run(['cua-driver','call','list_windows'], capture_output=True, text=True)
        for w in json.loads(p.stdout).get('windows',[]):
            if w.get('pid')==self.pid and w.get('title','') and w.get('window_id')==self.wid:
                b = w.get('bounds',{})
                self._wx, self._wy = b.get('x',0), b.get('y',0)
                break
        # Toolbar height via AX tree
        p = subprocess.run(['cua-driver','call','get_window_state',
            json.dumps({'pid':self.pid,'window_id':self.wid})], capture_output=True, text=True)
        tree = json.loads(p.stdout).get('tree_markdown','')
        for line in tree.split('\n'):
            m = re.search(r'AXWebArea.*@\((\d+),(\d+)', line)
            if m:
                self._toolbar = int(m.group(2))
                break

    def js(self, code):
        p = subprocess.run(['cua-driver','page', json.dumps({
            'pid':self.pid,'window_id':self.wid,'action':'execute_javascript','javascript':code
        })], capture_output=True, text=True, timeout=10)
        out = p.stdout
        return out.split('```')[1].strip() if '```' in out else ''

    def dom_to_window(self, x, y):
        """Convert DOM (viewport) coordinates to window coordinates"""
        return x, y + self._toolbar

    def drag(self, fx, fy, tx, ty):
        """Execute drag via cua-driver CGEvent"""
        p = subprocess.run(['cua-driver','call','drag', json.dumps({
            'pid':self.pid,'from_x':fx,'from_y':fy,'to_x':tx,'to_y':ty,
            'speed':80,'steps':80
        })], capture_output=True, text=True, timeout=30)
        return 'Posted drag' in p.stdout

    def solve_slide(self):
        """Solve slide captcha (gc-drag-block on gc-drag-slide-bar)"""
        self.js("document.querySelector('.go-captcha')?.scrollIntoView({behavior:'instant',block:'center'})")
        time.sleep(0.5)
        raw = self.js('''(()=>{
            const b=document.querySelector('.gc-drag-block'),s=document.querySelector('.gc-drag-slide-bar');
            if(!b||!s)return'{}';
            const br=b.getBoundingClientRect(),sr=s.getBoundingClientRect();
            return JSON.stringify({fx:Math.round(br.left+br.width/2),fy:Math.round(br.top+br.height/2),
                tx:Math.round(sr.right-br.width/2-2),ty:Math.round(sr.top+sr.height/2)});
        })()''')
        if raw == '{}': return False
        d = json.loads(raw)
        fx, fy = self.dom_to_window(d['fx'], d['fy'])
        tx, ty = self.dom_to_window(d['tx'], d['ty'])
        self.drag(fx, fy, tx, ty)
        time.sleep(2)
        r = json.loads(self.js('''(()=>{
            const b=document.querySelector('.gc-drag-block');
            return JSON.stringify({left:b?.style?.left||'?'});
        })()'''))
        return r.get('left') == '0px'

    def solve_dragdrop(self, drag_selector, drop_selector):
        """Generic: drag element from drag_selector to drop_selector"""
        self.js(f"document.querySelector('{drag_selector}')?.scrollIntoView({{behavior:'instant',block:'center'}})")
        time.sleep(0.5)
        raw = self.js(f'''(()=>{{
            const src=document.querySelector('{drag_selector}'),tgt=document.querySelector('{drop_selector}');
            if(!src||!tgt)return'{{}}';
            const sr=src.getBoundingClientRect(),tr=tgt.getBoundingClientRect();
            return JSON.stringify({{fx:Math.round(sr.left+sr.width/2),fy:Math.round(sr.top+sr.height/2),
                tx:Math.round(tr.left+tr.width/2),ty:Math.round(tr.top+tr.height/2)}});
        }})()''')
        if raw == '{}': return False
        d = json.loads(raw)
        fx, fy = self.dom_to_window(d['fx'], d['fy'])
        tx, ty = self.dom_to_window(d['tx'], d['ty'])
        return self.drag(fx, fy, tx, ty)
