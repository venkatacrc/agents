// Draws the app icon (the agent loop: an arrow circling through think, act and observe, with
// "act" lit) and writes an .iconset folder for iconutil, or with --web the PNGs for the web app
// (icon-192/512 plus a full-bleed maskable-512 for Android).
// Usage: swift scripts/make_icon.swift OUT.iconset
//        swift scripts/make_icon.swift --web web/icons
import AppKit

enum Style { case mac, web, maskable }

let web = CommandLine.arguments[1] == "--web"
let out = URL(fileURLWithPath: CommandLine.arguments[web ? 2 : 1], isDirectory: true)
try FileManager.default.createDirectory(at: out, withIntermediateDirectories: true)

func point(_ c: NSPoint, _ r: CGFloat, _ degrees: CGFloat) -> NSPoint {
    let a = degrees * .pi / 180
    return NSPoint(x: c.x + r * cos(a), y: c.y + r * sin(a))
}

func render(_ px: Int, _ style: Style = .mac) -> Data {
    let rep = NSBitmapImageRep(
        bitmapDataPlanes: nil, pixelsWide: px, pixelsHigh: px, bitsPerSample: 8,
        samplesPerPixel: 4, hasAlpha: true, isPlanar: false, colorSpaceName: .deviceRGB,
        bytesPerRow: 0, bitsPerPixel: 0)!
    NSGraphicsContext.saveGraphicsState()
    NSGraphicsContext.current = NSGraphicsContext(bitmapImageRep: rep)
    let s = CGFloat(px)

    // macOS icon grid: the tile is inset ~10% with a ~22% corner radius. Android crops
    // maskable icons to its own shape, keeping only the central 80% circle.
    let inset: CGFloat = style == .mac ? 0.1 : style == .web ? 0.02 : 0
    let tile = NSRect(x: s * inset, y: s * inset, width: s * (1 - 2 * inset), height: s * (1 - 2 * inset))
    let radius = style == .maskable ? 0 : tile.width * 0.225
    NSGradient(colors: [
        NSColor(red: 0.49, green: 0.42, blue: 0.96, alpha: 1),
        NSColor(red: 0.24, green: 0.17, blue: 0.66, alpha: 1),
    ])!.draw(in: NSBezierPath(roundedRect: tile, xRadius: radius, yRadius: radius), angle: -90)

    let center = NSPoint(x: tile.midX, y: tile.midY)
    let r = (style == .maskable ? s * 0.2 : tile.width * 0.25)
    let ink = NSColor(red: 1.0, green: 0.99, blue: 0.96, alpha: 1)

    // The loop: an arc from the top, clockwise almost all the way round, ending in an arrowhead.
    let ring = NSBezierPath()
    ring.appendArc(withCenter: center, radius: r, startAngle: 70, endAngle: 110, clockwise: true)
    ring.lineWidth = r * 0.16
    ring.lineCapStyle = .round
    let tint = NSColor(red: 0.80, green: 0.77, blue: 0.99, alpha: 1)
    tint.setStroke()
    ring.stroke()

    let tip = point(center, r, 110)
    let head = NSBezierPath()
    let size = r * 0.36
    // A clockwise arc ending at 110 degrees is heading right and slightly up.
    head.move(to: NSPoint(x: tip.x - size * 0.2, y: tip.y + size * 0.75))
    head.line(to: NSPoint(x: tip.x - size * 0.2, y: tip.y - size * 0.75))
    head.line(to: NSPoint(x: tip.x + size * 0.95, y: tip.y + size * 0.3))
    head.close()
    tint.setFill()
    head.fill()

    // Think, act, observe: three nodes on the loop; "act" (bottom right) is lit.
    let shadow = NSShadow()
    shadow.shadowColor = NSColor(white: 0, alpha: 0.3)
    shadow.shadowOffset = NSSize(width: 0, height: -s * 0.01)
    shadow.shadowBlurRadius = s * 0.02
    for (angle, lit) in [(CGFloat(10), false), (CGFloat(-90), true), (CGFloat(190), false)] {
        let c = point(center, r, angle)
        let d = r * (lit ? 0.5 : 0.36)
        NSGraphicsContext.saveGraphicsState()
        if lit { shadow.set() }
        (lit ? ink : tint.blended(withFraction: 0.5, of: ink)!).setFill()
        NSBezierPath(ovalIn: NSRect(x: c.x - d / 2, y: c.y - d / 2, width: d, height: d)).fill()
        NSGraphicsContext.restoreGraphicsState()
    }

    NSGraphicsContext.restoreGraphicsState()
    return rep.representation(using: .png, properties: [:])!
}

if web {
    try render(192, .web).write(to: out.appendingPathComponent("icon-192.png"))
    try render(512, .web).write(to: out.appendingPathComponent("icon-512.png"))
    try render(512, .maskable).write(to: out.appendingPathComponent("maskable-512.png"))
} else {
    for size in [16, 32, 128, 256, 512] {
        try render(size).write(to: out.appendingPathComponent("icon_\(size)x\(size).png"))
        try render(size * 2).write(to: out.appendingPathComponent("icon_\(size)x\(size)@2x.png"))
    }
}
