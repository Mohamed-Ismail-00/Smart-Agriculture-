/**
 * utils/farmCalendar.js
 * The Coptic calendar that Egyptian farmers plant and harvest by, and the Nile Delta seasons.
 */

import sowingWheat from "../assets/photos/sowing-wheat.jpg";
import greenFields from "../assets/photos/green-fields.jpg";
import wheatHarvest from "../assets/photos/wheat-harvest.jpg";
import wheatSheaves from "../assets/photos/wheat-sheaves.jpg";
import ricePlanting from "../assets/photos/rice-planting.jpg";
import riceHarvest from "../assets/photos/rice-harvest.jpg";

const PHOTOS = {
  sowing: { src: sowingWheat, alt: "An Egyptian farmer with his hoe in a green field" },
  green: { src: greenFields, alt: "A farmer on his donkey beside the fields" },
  wheatHarvest: { src: wheatHarvest, alt: "A farmer holding a sickle in ripe wheat" },
  sheaves: { src: wheatSheaves, alt: "A farmer carrying a sheaf of harvested wheat" },
  ricePlanting: { src: ricePlanting, alt: "A farmer planting rice in a flooded field" },
  riceHarvest: { src: riceHarvest, alt: "A farmer gathering harvested rice" },
};

// The 13 Coptic months: name, the farmers' proverb, what happens in Delta fields, and its photograph.
const MONTHS = [
  { ar: "توت", en: "Tout", proverb: "توت يقول للحر موت", field: "Rice and cotton harvest, land made ready for winter", photo: "riceHarvest" },
  { ar: "بابه", en: "Baba", proverb: "بابه خش واقفل الدرابة", field: "Clover and wheat sowing begins", photo: "sowing" },
  { ar: "هاتور", en: "Hatour", proverb: "هاتور أبو الدهب المنتور", field: "The month to sow wheat in the Delta", photo: "sowing" },
  { ar: "كيهك", en: "Kiahk", proverb: "كيهك صباحك مساك", field: "Short days, winter crops take root", photo: "sowing" },
  { ar: "طوبة", en: "Touba", proverb: "طوبة تخلي الصبية كركوبة", field: "The coldest month, wheat and clover grow", photo: "green" },
  { ar: "أمشير", en: "Amshir", proverb: "أمشير أبو الزعابيب الكتير", field: "The windy month, clover is cut again", photo: "green" },
  { ar: "برمهات", en: "Baramhat", proverb: "برمهات روح الغيط وهات", field: "Winter crops ripen, the first harvests", photo: "green" },
  { ar: "برمودة", en: "Baramouda", proverb: "برمودة دق بالعمودة", field: "Wheat harvest and threshing", photo: "wheatHarvest" },
  { ar: "بشنس", en: "Bashans", proverb: "بشنس يكنس الغيط كنس", field: "Fields cleared, summer crops sown", photo: "sheaves" },
  { ar: "بؤونة", en: "Paona", proverb: "بؤونة تكتر فيه الحرارة الملعونة", field: "The heat rises, rice is transplanted", photo: "ricePlanting" },
  { ar: "أبيب", en: "Abib", proverb: "أبيب فيه العنب يطيب", field: "Summer crops grow, grapes ripen", photo: "ricePlanting" },
  { ar: "مسرى", en: "Mesra", proverb: "مسرى تجري فيه كل ترعة عسرة", field: "Peak summer, the canals run full", photo: "riceHarvest" },
  { ar: "النسيء", en: "Nasie", proverb: null, field: "The short month that closes the Coptic year", photo: "riceHarvest" },
];

const COPTIC_EPOCH = 103605; // Rata Die of 1 Tout, year 1

function rataDie(date) {
  const y = date.getFullYear(), m = date.getMonth() + 1, d = date.getDate();
  const leap = (y % 4 === 0 && y % 100 !== 0) || y % 400 === 0;
  return 365 * (y - 1) + Math.floor((y - 1) / 4) - Math.floor((y - 1) / 100) + Math.floor((y - 1) / 400)
    + Math.floor((367 * m - 362) / 12) + (m <= 2 ? 0 : leap ? -1 : -2) + d;
}

/** Coptic date of a Gregorian date: { year, month (1-13), day }. */
export function copticDate(date = new Date()) {
  const rd = rataDie(date);
  const year = Math.floor((4 * (rd - COPTIC_EPOCH) + 1463) / 1461);
  const yearStart = COPTIC_EPOCH - 1 + 365 * (year - 1) + Math.floor(year / 4) + 1;
  const month = Math.floor((rd - yearStart) / 30) + 1;
  const day = rd - yearStart - 30 * (month - 1) + 1;
  return { year, month, day };
}

/** The farming month of today: names, proverb, field work and photograph. */
export function farmMonth(date = new Date()) {
  const c = copticDate(date);
  const m = MONTHS[c.month - 1];
  return { ...c, ...m, photo: PHOTOS[m.photo] };
}

/** The growing season that started most recently: winter 1 Oct – 31 May, summer 1 May – 31 Oct. */
export function currentSeason(date = new Date()) {
  const y = date.getFullYear(), month = date.getMonth();
  const season = month >= 9
    ? { name: "Winter", label: `${y}/${String(y + 1).slice(2)}`, start: new Date(y, 9, 1), end: new Date(y + 1, 4, 31) }
    : month >= 4
      ? { name: "Summer", label: `${y}`, start: new Date(y, 4, 1), end: new Date(y, 9, 31) }
      : { name: "Winter", label: `${y - 1}/${String(y).slice(2)}`, start: new Date(y - 1, 9, 1), end: new Date(y, 4, 31) };
  const day = Math.floor((date - season.start) / 86_400_000) + 1;
  const length = Math.floor((season.end - season.start) / 86_400_000) + 1;
  return { ...season, day, length, share: Math.min(1, day / length) };
}

export const PHOTO_CREDITS =
  "Photographs: Wikimedia Commons, Wiki Loves Africa (Egypt), CC BY-SA 4.0, by Evon2023, Mona Hassan Abo-Abda, Ahmed Flex777 and Doaa Adel.";
