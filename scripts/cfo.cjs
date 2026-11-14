// node scripts/cfo.cjs [--pitch]; same economics function as the inline UI.
const r = require('../data/replay_comparison.json');
const assumptions = require('../prezero_config.json').economics;
const calc = require('../src/prezero/economics.js');
const c = calc(r, assumptions);
if (process.argv.includes('--pitch')) {
  const fmt = n => n.toLocaleString('de-DE',{minimumFractionDigits:1,maximumFractionDigits:1});
  console.log('Bei '+fmt(r.observed.mean_fill_pct)+' % gemessener Füllung wurden die Behälter geleert. Im Replay erreicht GlasRoute '+fmt(r.optimized.mean_fill_pct)+' %. Gegenüber denselben Besuchstagen mit identischem modelliertem Glaszufluss sammelt GlasRoute '+fmt((r.optimized.inventory.collected_kg-r.historical.inventory.collected_kg)/1000)+' t mehr. Die modellierten Kosten '+(c.difference<0?'steigen':'sinken')+' um '+fmt(Math.abs(c.difference)/r.operating_days)+' €/Betriebstag. Keine belegte Flottenreduktion.');
} else console.log(JSON.stringify(c,null,2));
