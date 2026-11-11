/*
 * Rendu d'une vidéo image par image (30 i/s) : node rendre.js <video> <langue> <h|v> [apercu]
 * apercu : quelques images clés en PNG (pour vérifier) ; sinon MP4 muet (H.264) dans rendus/.
 */
const { chromium } = require("playwright-core");
const { spawn } = require("child_process");
const fs = require("fs");
const path = require("path");

const [video, langue, format, mode] = process.argv.slice(2);
const ICI = __dirname;
const FFMPEG = require("ffmpeg-static");
const IPS = 30;
const textes = JSON.parse(fs.readFileSync(`${ICI}/textes.json`, "utf8"));
const placements = JSON.parse(fs.readFileSync(`${ICI}/voix/placements.json`, "utf8"));
const W = format === "h" ? 1920 : 1080;
const H = format === "h" ? 1080 : 1920;

(async () => {
  const navigateur = await chromium.launch({ channel: "chrome", args: ["--allow-file-access-from-files"] });
  const page = await navigateur.newPage({ viewport: { width: W, height: H }, deviceScaleFactor: 1 });
  const donnees = { t: textes[langue], scenes: placements[langue][video].scenes, langue };
  await page.addInitScript((d) => { window.DONNEES = d; }, donnees);
  page.on("pageerror", (e) => console.error("Erreur page :", e.message));
  await page.goto(`file://${ICI}/studio/studio.html?v=${video}&f=${format}`);
  await page.waitForFunction(() => window.pret);
  await page.evaluate(() => window.pret);

  if (mode === "apercu") {
    const dossier = `${ICI}/apercus/${video}-${langue}-${format}`;
    fs.mkdirSync(dossier, { recursive: true });
    const scenes = placements[langue][video].scenes;
    const instants = [];
    Object.values(scenes).forEach(([a, b]) => instants.push(a + 0.15 * (b - a), a + 0.6 * (b - a), b - 0.25));
    for (const t of instants) {
      await page.evaluate((x) => window.seek(x), t);
      await page.screenshot({ path: `${dossier}/${t.toFixed(2).padStart(5, "0")}.jpg`, type: "jpeg", quality: 80 });
    }
    console.log("aperçu :", dossier);
    await navigateur.close();
    return;
  }

  fs.mkdirSync(`${ICI}/rendus`, { recursive: true });
  const sortie = `${ICI}/rendus/${video}-${langue}-${format}-muet.mp4`;
  const ff = spawn(FFMPEG, ["-y", "-loglevel", "error", "-f", "image2pipe", "-framerate", String(IPS), "-c:v", "mjpeg", "-i", "-",
    "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p", "-movflags", "+faststart", sortie]);
  ff.stderr.on("data", (d) => process.stderr.write(d));
  const total = 30 * IPS;
  for (let i = 0; i < total; i++) {
    await page.evaluate((x) => window.seek(x), i / IPS);
    const image = await page.screenshot({ type: "jpeg", quality: 92 });
    if (!ff.stdin.write(image)) await new Promise((r) => ff.stdin.once("drain", r));
  }
  ff.stdin.end();
  await new Promise((r) => ff.on("close", r));
  await navigateur.close();
  console.log("vidéo :", path.basename(sortie));
  process.exit(0);
})();
