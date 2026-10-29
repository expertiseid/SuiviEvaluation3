// Recense les textes à traduire : ceux de l'interface (voc("…"), voc`…${x}…`, t(…)) et les
// messages du serveur affichés tels quels (erreurs de validation…). Écrit src/i18n/sources.json
// (liste triée), src/i18n/contextes.json (pour chaque texte, les fichiers où il apparaît, afin que
// l'écran Langues dise où il s'affiche) et indique, pour chaque langue, les textes encore sans traduction.
// Usage : d'abord relever les messages du serveur (voir scripts/textes_serveur.py), puis
// dans le conteneur frontend : node scripts/extraire-textes.cjs
const ts = require("typescript");
const fs = require("fs");
const path = require("path");

const SRC = path.join(__dirname, "..", "src");
const textes = new Set();
const contextes = {};
function relever(texte, lieu) {
  textes.add(texte);
  (contextes[texte] ??= new Set()).add(lieu);
}

function fichiers(dossier, extensions) {
  return fs.readdirSync(dossier, { withFileTypes: true }).flatMap((e) => {
    const p = path.join(dossier, e.name);
    if (e.isDirectory()) return ["node_modules", "migrations", "__pycache__"].includes(e.name) ? [] : fichiers(p, extensions);
    return extensions.some((x) => e.name.endsWith(x)) && !e.name.endsWith(".d.ts") ? [p] : [];
  });
}

const estVoc = (n) => ts.isIdentifier(n) && (n.text === "voc" || n.text === "t");
for (const fichier of fichiers(SRC, [".ts", ".tsx"])) {
  const lieu = path.relative(SRC, fichier).split(path.sep).join("/");
  const source = ts.createSourceFile(fichier, fs.readFileSync(fichier, "utf8"), ts.ScriptTarget.Latest, true,
    fichier.endsWith(".tsx") ? ts.ScriptKind.TSX : ts.ScriptKind.TS);
  (function visiter(n) {
    if (ts.isCallExpression(n) && estVoc(n.expression) && n.arguments[0] &&
        (ts.isStringLiteral(n.arguments[0]) || ts.isNoSubstitutionTemplateLiteral(n.arguments[0]))) {
      relever(n.arguments[0].text, lieu);
    }
    if (ts.isTaggedTemplateExpression(n) && estVoc(n.tag)) {
      const g = n.template;
      if (ts.isNoSubstitutionTemplateLiteral(g)) relever(g.text, lieu);
      else relever(g.head.text + g.templateSpans.map((s, i) => `{${i}}` + s.literal.text).join(""), lieu);
    }
    ts.forEachChild(n, visiter);
  })(source);
}

// Messages du serveur : relevés par scripts/textes_serveur.py dans src/i18n/serveur.json
// (les f-strings y sont des modèles {0}, {1}… que l'interface reconnaît).
const serveur = path.join(SRC, "i18n", "serveur.json");
if (fs.existsSync(serveur)) for (const texte of JSON.parse(fs.readFileSync(serveur, "utf8"))) relever(texte, "serveur");

const liste = [...textes].filter((x) => x.trim()).sort((a, b) => a.localeCompare(b, "fr"));
fs.writeFileSync(path.join(SRC, "i18n", "sources.json"), JSON.stringify(liste, null, 1) + "\n");
fs.writeFileSync(path.join(SRC, "i18n", "contextes.json"),
  JSON.stringify(Object.fromEntries(liste.map((x) => [x, [...contextes[x]].sort()])), null, 1) + "\n");
console.log(`${liste.length} textes`);
for (const langue of ["en", "ar", "es", "de"]) {
  const chemin = path.join(SRC, "i18n", `${langue}.json`);
  const catalogue = fs.existsSync(chemin) ? JSON.parse(fs.readFileSync(chemin, "utf8")) : {};
  const manquants = liste.filter((x) => !(x in catalogue));
  console.log(`${langue} : ${liste.length - manquants.length} traduits, ${manquants.length} manquants`);
}
