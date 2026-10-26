const { spawn } = require('child_process');
const http = require('http');

const edgePath = "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe";
const htmlPath = "file:///" + __dirname.replace(/\\/g, '/') + "/index.html";

const proc = spawn(edgePath, [
  '--headless=new',
  '--remote-debugging-port=9235',
  '--disable-gpu',
  htmlPath
]);

setTimeout(() => {
  http.get('http://127.0.0.1:9235/json', (res) => {
    let data = '';
    res.on('data', chunk => data += chunk);
    res.on('end', () => {
      try {
        const tabs = JSON.parse(data);
        const pageTab = tabs.find(t => t.type === 'page' && t.url.includes('index.html')) || tabs[0];
        const ws = new WebSocket(pageTab.webSocketDebuggerUrl);
        ws.onopen = () => {
          let id = 1;
          function send(method, params) {
            ws.send(JSON.stringify({ id: id++, method, params }));
          }
          ws.onmessage = (msg) => {
            const resp = JSON.parse(msg.data);
            if (resp.result) {
              if (resp.result.exceptionDetails) {
                console.error(JSON.stringify(resp.result.exceptionDetails));
                proc.kill();
                process.exit(1);
              } else if (resp.result.result) {
                console.log(JSON.stringify(resp.result.result.value));
                proc.kill();
                process.exit(0);
              }
            }
          };

          const evaluateCode = `
            (function() {
              const editor = document.getElementById('sourceEditor');
              const gutter = document.getElementById('lineNumbersGutter');
              const countPill = document.getElementById('editorLineCount');
              
              const results = {};
              
              // 1. Short 7 lines
              editor.value = '#include <stdio.h>\\n\\nint main() {\\n    int a = 1;\\n    printf(\\'%d\\', a);\\n    return 0;\\n}';
              updateLineNumbers();
              results.test1_7lines = {
                lineCount: editor.value.split('\\n').length,
                gutterDivs: gutter.children.length,
                gutterFirst: gutter.children[0].textContent,
                gutterLast: gutter.children[gutter.children.length - 1].textContent,
                pillText: countPill.textContent
              };
              
              // 2. 100 lines
              const l100 = [];
              for (let i = 1; i <= 100; i++) l100.push('int x_' + i + ' = ' + i + ';');
              editor.value = l100.join('\\n');
              updateLineNumbers();
              results.test2_100lines = {
                lineCount: editor.value.split('\\n').length,
                gutterDivs: gutter.children.length,
                gutterFirst: gutter.children[0].textContent,
                gutterLast: gutter.children[gutter.children.length - 1].textContent,
                pillText: countPill.textContent
              };
              
              // 3. Complete 5,000-line stress test with scroll to bottom
              const l5000 = [];
              for (let i = 1; i <= 5000; i++) l5000.push('int value_' + i + ' = ' + i + ';');
              editor.value = l5000.join('\\n');
              updateLineNumbers();
              editor.scrollTop = editor.scrollHeight;
              editor.dispatchEvent(new Event('scroll'));
              
              const gutterRect = gutter.getBoundingClientRect();
              const visibleLines = [];
              for (let i = 0; i < gutter.children.length; i++) {
                const r = gutter.children[i].getBoundingClientRect();
                if (r.bottom >= gutterRect.top && r.top <= gutterRect.bottom) {
                  visibleLines.push(gutter.children[i].textContent);
                }
              }
              results.test3_5000lines = {
                totalLines: editor.value.split('\\n').length,
                gutterDivs: gutter.children.length,
                editorScrollTop: editor.scrollTop,
                gutterScrollTop: gutter.scrollTop,
                visibleLinesCount: visibleLines.length,
                visibleFirst: visibleLines[0],
                visibleLast: visibleLines[visibleLines.length - 1],
                scrolledToFinal: parseInt(visibleLines[visibleLines.length - 1], 10) >= 4995
              };
              
              // 4. Blank lines and trailing newline
              editor.value = 'int a;\\n\\nint b;\\n';
              updateLineNumbers();
              results.test4_blankAndTrailing = {
                rawLines: editor.value.split('\\n'),
                totalLines: editor.value.split('\\n').length,
                gutterDivs: gutter.children.length,
                lastGutterText: gutter.children[gutter.children.length - 1].textContent
              };
              
              // 5. Pasting a short program after a large program
              editor.value = 'int shortProg = 42;\\nreturn 0;';
              onSourceInput();
              results.test5_pasteAfterLarge = {
                totalLines: editor.value.split('\\n').length,
                gutterDivs: gutter.children.length,
                gutterLast: gutter.children[gutter.children.length - 1].textContent,
                pillText: countPill.textContent
              };
              
              // 6. Loading a file and switching presets
              const presetSelect = document.getElementById('presetSelect');
              if (presetSelect && presetSelect.options.length > 1) {
                presetSelect.value = presetSelect.options[1].value;
                loadSelectedPreset();
                results.test6_switchPreset = {
                  totalLines: editor.value.split('\\n').length,
                  gutterDivs: gutter.children.length,
                  gutterLast: gutter.children[gutter.children.length - 1].textContent
                };
              }
              
              // 7. Syntax error near line 4,900 and jump to location
              const l4900 = [];
              for (let i = 1; i <= 4899; i++) l4900.push('int v_' + i + ' = ' + i + ';');
              l4900.push('int faulty = ;');
              for (let i = 4901; i <= 5000; i++) l4900.push('int v_' + i + ' = ' + i + ';');
              editor.value = l4900.join('\\n');
              updateLineNumbers();
              highlightOffendingSource(4900, 15, 'error', 'Syntax error');
              jumpToLocation(4900, 15);
              
              results.test7_jumpTo4900 = {
                targetLine: 4900,
                selectionStart: editor.selectionStart,
                selectionEnd: editor.selectionEnd,
                highlightedChildClass: gutter.children[4899].className,
                editorScrollTop: editor.scrollTop,
                gutterScrollTop: gutter.scrollTop,
                scrollSynchronized: Math.abs(editor.scrollTop - gutter.scrollTop) < 5
              };
              
              return results;
            })()
          `;

          send('Runtime.evaluate', {
            expression: evaluateCode,
            returnByValue: true
          });
        };
      } catch (err) {
        console.error('Err:', err);
        proc.kill();
        process.exit(1);
      }
    });
  }).on('error', (err) => {
    console.error('HTTP err:', err);
    proc.kill();
    process.exit(1);
  });
}, 2000);
