// scan_overflow.jsx — find every item that overflows the artboard and is NOT already
// inside a clipping group. Read-only: never modifies the document.
//
// Usage (always via run_headless.ps1 so the script runs from the AI drive and no
// modal "File not found" dialog blocks Illustrator):
//   powershell -ExecutionPolicy Bypass -File run_headless.ps1 `
//       -Jsx scan_overflow.jsx -Log C:\ai\jobs\_overflow.txt -TimeoutSec 300
//
// NOTE: the CONTENT of this file is ASCII-only (the file itself carries a UTF-8
// BOM, which is good: ExtendScript then reads it as UTF-8). Why ASCII-only?
// Without a BOM ExtendScript reads .jsx as system ANSI and non-ASCII literals
// get mangled - a Chinese layer-name literal made getByName() return
// undefined. Layer names are READ here, never COMPARED against a literal.

#target illustrator
#targetengine "session"

// ====== config ======
var DOC = "C:/ai/jobs/_scan.ai";       // document to inspect
var LOG = "C:/ai/jobs/_overflow.txt";   // log output
var EPS = 0.5;                          // tolerance in document units
// ===================

var f = new File(LOG);
f.encoding = "UTF-8";
f.open("w");
function log(s) { try { f.writeln(s); f.flush(); } catch (e) {} }
function vbs(it) {
  var b = it.visibleBounds;
  return "L=" + b[0].toFixed(2) + " T=" + b[1].toFixed(2) +
         " R=" + b[2].toFixed(2) + " B=" + b[3].toFixed(2);
}

try {
  app.userInteractionLevel = UserInteractionLevel.DONTDISPLAYALERTS;
  var doc = app.open(new File(DOC));
  var art = doc.artboards[0].artboardRect;      // [left, top, right, bottom], y is UP
  var L = art[0], R = art[2], T = art[1], B = art[3];
  log("document : " + DOC);
  log("artboard : L=" + L + " R=" + R + " T=" + T + " B=" + B);

  var stack = [], issues = 0;
  for (var li = 0; li < doc.layers.length; li++) {
    var ly = doc.layers[li];
    log("=== LAYER '" + ly.name + "' ===");
    for (var pi = 0; pi < ly.pageItems.length; pi++) {
      stack.push({ it: ly.pageItems[pi], layer: ly.name });
    }
  }

  while (stack.length) {
    var e = stack.pop();
    if (e.it.typename === "GroupItem") {
      if (e.it.clipped) {                       // already clipped -> skip its content
        log("  (skip clipped group '" + e.it.name + "' in layer '" + e.layer + "')");
        continue;
      }
      for (var gi = e.it.pageItems.length - 1; gi >= 0; gi--) {
        stack.push({ it: e.it.pageItems[gi], layer: e.layer });
      }
      continue;
    }
    var b = e.it.visibleBounds;
    var over = [];
    if (b[0] < L - EPS) over.push("left " + (L - b[0]).toFixed(2));
    if (b[2] > R + EPS) over.push("right " + (b[2] - R).toFixed(2));
    if (b[1] > T + EPS) over.push("top " + (b[1] - T).toFixed(2));
    if (b[3] < B - EPS) over.push("bottom " + (B - b[3]).toFixed(2));
    if (over.length) {
      issues++;
      log("  OVERFLOW [" + e.layer + "] " + e.it.typename + " '" + e.it.name + "' " + vbs(e.it));
      log("      exceeds artboard by: " + over.join(" / "));
    }
  }
  log("unclipped overflow items: " + issues);

  doc.close(SaveOptions.DONOTSAVECHANGES);
  log("done");
} catch (e) {
  log("ERROR: " + (e && e.message ? e.message : e));
}
try { f.close(); } catch (e) {}
try { app.quit(); } catch (e) {}
