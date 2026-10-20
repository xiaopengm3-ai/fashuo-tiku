import Foundation
import Vision
import AppKit
import PDFKit

// usage: ocr <pdf> <startPage> <endPage> <out.txt> [dpiScale]
let args = CommandLine.arguments
guard args.count >= 5 else { fputs("usage: ocr pdf start end out\n", stderr); exit(1) }
let path = args[1]
let start = Int(args[2]) ?? 0
let end = Int(args[3]) ?? 1
let outPath = args[4]
let scale: CGFloat = args.count > 5 ? CGFloat(Double(args[5]) ?? 2.0) : 2.0
guard let doc = PDFDocument(url: URL(fileURLWithPath: path)) else { fputs("cannot open\n", stderr); exit(1) }
var out = ""
let pageCount = min(end, doc.pageCount)
for i in max(0,start)..<pageCount {
    guard let page = doc.page(at: i) else { continue }
    let bounds = page.bounds(for: .mediaBox)
    let w = Int(bounds.width * scale), h = Int(bounds.height * scale)
    guard let rep = NSBitmapImageRep(bitmapDataPlanes: nil, pixelsWide: w, pixelsHigh: h, bitsPerSample: 8, samplesPerPixel: 4, hasAlpha: true, isPlanar: false, colorSpaceName: .deviceRGB, bytesPerRow: 0, bitsPerPixel: 0) else { continue }
    NSGraphicsContext.saveGraphicsState()
    guard let gc = NSGraphicsContext(bitmapImageRep: rep) else { continue }
    NSGraphicsContext.current = gc
    let ctx = gc.cgContext
    ctx.setFillColor(NSColor.white.cgColor)
    ctx.fill(CGRect(x: 0, y: 0, width: w, height: h))
    ctx.scaleBy(x: scale, y: scale)
    page.draw(with: .mediaBox, to: ctx)
    gc.flushGraphics()
    NSGraphicsContext.restoreGraphicsState()
    guard let cg = rep.cgImage else { continue }
    let req = VNRecognizeTextRequest()
    req.recognitionLevel = .accurate
    req.recognitionLanguages = ["zh-Hans", "en-US"]
    req.usesLanguageCorrection = true
    let handler = VNImageRequestHandler(cgImage: cg, options: [:])
    do { try handler.perform([req]) } catch { fputs("ocr fail page \(i): \(error)\n", stderr); continue }
    var items: [(Double, Double, Double, Double, String)] = []
    for obs in req.results ?? [] {
        if let c = obs.topCandidates(1).first {
            let b = obs.boundingBox
            items.append((Double(b.minX), Double(1 - b.maxY), Double(b.maxX), Double(1 - b.minY), c.string))
        }
    }
    // sort top->bottom; for same-ish row left->right
    items.sort { a, b in
        if abs(a.1 - b.1) > 0.008 { return a.1 < b.1 }
        return a.0 < b.0
    }
    out += "===== PAGE \(i+1) =====\n"
    for it in items { out += it.4 + "\n" }
    out += "\n"
    fputs("page \(i+1)/\(pageCount)\n", stderr)
}
try? out.write(toFile: outPath, atomically: true, encoding: .utf8)
