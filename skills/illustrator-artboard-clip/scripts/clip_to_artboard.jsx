// clip_to_artboard.jsx — trim assets to the artboard with a CLIPPING MASK.
//
// Technique: do NOT crop the image data. Build a rectangle the size of the
// artboard, put it on top of the asset inside a group and turn the group into a
// clipping group. The asset keeps its pixels, its placement and its size; only
// the part outside the artboard stops being visible. Fully reversible.
//
// Usage (via run_headless.ps1 - same drive as Illustrator, otherwise a modal
// "File not found" dialog blocks the run):
//   powershell -ExecutionPolicy Bypass -File run_headless.ps1 `
//       -Jsx clip_to_artboard.jsx -Log C:\ai\jobs\_clip.txt -TimeoutSec 420
//
// API notes that this script encodes (Illustrator 2026 / build 30):
//   - clipping group needs AT LEAST TWO items, and the clip path must be the
//     TOPMOST item inside the group; otherwise clipped=true throws
//     "There must be at least two page items in a group to create a mask"
//   - move an item INTO a group with PLACEATEND (bottom of the group);
//     PLACEAFTER means "after that item" and would push it OUT of the group
//   - doc.pageItems index 0 is the FRONTMOST item, not the last one
//   - coordinates are y-up: artboardRect = [left, top, right, bottom]
//
// NOTE: ASCII-only on purpose (no UTF-8 BOM -> ExtendScript reads ANSI).

#target illustrator
#targetengine "session"

// ====== config ======
var DOC = "C:/ai/jobs/_work.ai";       // source document
var OUT = "C:/ai/jobs/_clip_out.ai";   // result document
var LOG = "C:/ai/jobs/_clip.txt";      // log output
var EPS = 0.5;                         // tolerance in document units
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
  var art = doc.artboards[0].artboardRect;
  var L = art[0], R = art[2], T = art[1], B = art[3];
  log("source  : " + DOC);
  log("artboard: L=" + L + " R=" + R + " T=" + T + " B=" + B);

  // ---- collect targets: overflow items that are not already inside a clipped group
  var jobs = [], stack = [];
  for (var li = 0; li < doc.layers.length; li++) {
    var ly = doc.layers[li];
    for (var pi = 0; pi < ly.pageItems.length; pi++) {
      stack.push({ it: ly.pageItems[pi], layer: ly.name });
    }
  }
  while (stack.length) {
    var e = stack.pop();
    if (e.it.typename === "GroupItem") {
      if (e.it.clipped) continue;
      for (var gi = e.it.pageItems.length - 1; gi >= 0; gi--) {
        stack.push({ it: e.it.pageItems[gi], layer: e.layer });
      }
      continue;
    }
    var b = e.it.visibleBounds;
    if (b[0] < L - EPS || b[2] > R + EPS || b[1] > T + EPS || b[3] < B - EPS) {
      jobs.push({ item: e.it, parent: e.it.parent, layer: e.layer });
    }
  }
  log("targets to clip: " + jobs.length);
  for (var j = 0; j < jobs.length; j++) {
    log("   [" + jobs[j].layer + "] " + jobs[j].item.typename + " '" + jobs[j].item.name + "' " + vbs(jobs[j].item));
  }

  // ---- wrap each target into an artboard clipping group
  for (var j2 = 0; j2 < jobs.length; j2++) {
    var target = jobs[j2].item, parent = jobs[j2].parent;

    // remember the stacking neighbourhood (pageItems[0] = frontmost)
    var sibs = [], idx = -1;
    for (var s = 0; s < parent.pageItems.length; s++) sibs.push(parent.pageItems[s]);
    for (var s2 = 0; s2 < sibs.length; s2++) if (sibs[s2] === target) idx = s2;
    var frontSibling = (idx > 0) ? sibs[idx - 1] : null;

    var clipPath = doc.pathItems.rectangle(art[1], art[0], art[2] - art[0], art[1] - art[3]);
    clipPath.name = "artboard-clip";
    var grp = doc.groupItems.add();
    grp.name = "artboard-clip-group";
    clipPath.move(grp, ElementPlacement.PLACEATBEGINNING);   // clip path on top
    target.move(grp, ElementPlacement.PLACEATEND);           // asset below it
    grp.clipped = true;                                      // -> clipping mask

    // put the group back at the asset's z position
    grp.move(parent, ElementPlacement.PLACEATEND);
    if (frontSibling) grp.move(frontSibling, ElementPlacement.PLACEAFTER);
    else grp.move(parent, ElementPlacement.PLACEATBEGINNING);
    log("clipped " + target.typename + " -> group '" + grp.name + "' clipped=" + grp.clipped + " (layer '" + jobs[j2].layer + "')");
  }

  // ---- stacking report
  for (var li2 = 0; li2 < doc.layers.length; li2++) {
    var ly2 = doc.layers[li2];
    log("LAYER '" + ly2.name + "' (" + ly2.pageItems.length + " top items, back -> front)");
    for (var pi2 = ly2.pageItems.length - 1; pi2 >= 0; pi2--) {
      var t2 = ly2.pageItems[pi2];
      log("   " + t2.typename + " '" + t2.name + "'" +
          (t2.typename === "GroupItem" ? " clipped=" + t2.clipped : "") + " " + vbs(t2));
    }
  }

  var opts = new IllustratorSaveOptions();
  doc.saveAs(new File(OUT), opts);
  log("saved: " + OUT);
  doc.close(SaveOptions.DONOTSAVECHANGES);
  log("done");
} catch (e) {
  log("ERROR: " + (e && e.message ? e.message : e));
}
try { f.close(); } catch (e) {}
try { app.quit(); } catch (e) {}
