import type { UMCPreviewObjectType } from '@umc-shared/types'

export const huObjectTypeLabels: Record<UMCPreviewObjectType, string> = {
  marker: 'Jelölő',
  heart: 'Szív',
  star: 'Csillag',
  pin: 'Kitűző',
  text: 'Szöveg',
}

export const huObjectLayerLabels: Record<string, string> = {
  roads: 'Utak',
  labels: 'Feliratok',
  buildings: 'Épületek',
  water: 'Vízfelületek',
  stars: 'Csillagok',
  constellations: 'Csillagképek',
  grid: 'Rácsvonalak',
}

export const huPaletteLabels: Record<string, string> = {
  'heritage-sand': 'Örökség homok',
  'graphite-ivory': 'Grafit elefántcsont',
  'night-gilded': 'Aranyozott éj',
  'amber-mineral': 'Borostyán ásvány',
}

export const huTemplateLabels: Record<string, string> = {
  'city-signature': 'Városi aláírás',
  'building-elevation': 'Épület homlokzat',
  'stellar-classic': 'Klasszikus csillagtérkép',
}

export const huToneLabels: Record<string, string> = {
  classic: 'Klasszikus',
  editorial: 'Szerkesztőségi',
  night: 'Éjszakai',
}

export const huLineWeightLabels: Record<string, string> = {
  balanced: 'Kiegyensúlyozott',
  fine: 'Finom',
}

export const huOrientationLabels: Record<string, string> = {
  portrait: 'Álló',
  landscape: 'Fekvő',
}

export const huModuleStatusLabels: Record<string, string> = {
  foundation: 'Alapmodul',
}

export const huUiText = {
  brand: 'Univerzális Térkép Konfigurátor',
  heroTitle: 'Prémium Poszter Alapok',
  heroSubtitle: 'Készítsd el a saját történeted',
  posterTitleLabel: 'Poszter címe',
  activeModule: 'Aktív modul',
  architectureModeOnly: 'Csak architektúra mód',
  interactivePreview: 'Interaktív előnézet',
  resetViewport: 'Visszaállítás',
  loadingPreview: 'Előnézet betöltése...',
  cityNotFound: 'A megadott város nem található',
  previewGenerationFailed: 'Az előnézet generálása sikertelen',
  generatePreviewHint: 'Kattints a Generálás gombra a várostérkép előnézet elkészítéséhez.',
  viewportHelp: 'Jobb klikk vagy Szóköz nyomva tartása: pásztázás • Görgetés: nagyítás',
  objectSystem: 'Objektumrendszer',
  objectsPanel: 'Objektumpanel',
  placementTool: 'Elhelyezési eszköz',
  currentObjects: 'Aktív objektumok',
  noObjectsYet: 'Még nincs objektum. Kattints az előnézetbe az elhelyezéshez.',
  delete: 'Törlés',
  moduleSelectorTitle: 'Modulválasztó',
  moduleSelectorDescription: 'Válts városi, épület- és csillagtérkép alapok között.',
  locationSectionTitle: 'Helyszín',
  locationSectionDescription: 'Állítsd be a célhelyszínt a térkép előnézetéhez.',
  cityLabel: 'Város',
  cityPlaceholder: 'Adj meg várost, címet vagy koordinátát',
  generatePreview: 'Generálás',
  latitude: 'Szélesség',
  longitude: 'Hosszúság',
  notAvailable: 'nincs adat',
  objectsSectionTitle: 'Térképrétegek',
  objectsSectionDescription: 'Kapcsold be vagy ki a megjelenő térképrétegeket.',
  styleSectionTitle: 'Stílus',
  styleSectionDescription: 'Válaszd ki a vizuális stílus beállításait.',
  palette: 'Színpaletta',
  tone: 'Tónus',
  lineWeight: 'Vonalvastagság',
  templateSectionTitle: 'Elrendezés',
  templateSectionDescription: 'Válassz kompozíciós elrendezést a poszterhez.',
  template: 'Elrendezés',
  ratio: 'Arány',
  orientation: 'Tájolás',
  enterCityFirst: 'Előbb adj meg egy városnevet.',
  unknownPreviewError: 'Ismeretlen hiba történt az előnézet generálása közben.',
  stepLocation: 'Helyszín',
  stepStyle: 'Stílus',
  stepPosterText: 'Poszter szövege',
  stepObjects: 'Objektumok',
  stepReviewOrder: 'Áttekintés és rendelés',
  cityMap: 'Várostérkép',
  starMap: 'Csillagtérkép',
  cityStyleTitle: 'Várostérkép stílus',
  cityStyleMinimal: 'Minimál',
  cityStyleUrbanModern: 'Urban Modern (parcellák)',
  cityStyleBuildings: 'Épületek',
  recommendedPalette: 'Ajánlott színpaletta',
  radius: 'Rádiusz',
  radiusDescription: 'A térkép megjelenített területének sugara.',
  eventDate: 'Esemény dátuma',
  displayMode: 'Megjelenítés',
  gridMode: 'Rácsvonalak',
  constellationMode: 'Csillagképek',
  frame: 'Keret',
  frameNone: 'Keret nélkül',
  frameWood: 'Fa, barna',
  frameBlack: 'Fekete',
  frameWhite: 'Fehér',
  textCustomization: 'Szöveg testreszabása',
  posterTextTitle: 'Cím',
  posterTextSubtitle: 'Alcím',
  posterTextDate: 'Dátum (opcionális)',
  posterTextCustom: 'Egyedi szöveg (opcionális)',
  typographyStyleTitle: 'Szöveg elrendezése',
  textPosition: 'Szöveg pozíció',
  textPositionDescription: 'A tipográfiai blokk függőleges pozíciója.',
  textAppearanceSettings: 'Szöveg beállítások',
  textSize: 'Szöveg mérete',
  textStyle: 'Stílus',
  textWeight: 'Vastagság',
  textFont: 'Betűstílus',
  textColor: 'Szín',
  textStyleNormal: 'Normál',
  textStyleItalic: 'Dőlt',
  textWeightRegular: 'Normál',
  textWeightSemiBold: 'Semi Bold',
  textWeightBold: 'Bold',
  textColorBlack: 'Fekete',
  textColorGray: 'Szürke',
  textColorBrown: 'Barna',
  posterTextPlaceholderSubtitle: 'A város ahol találkoztunk',
  posterTextPlaceholderDate: '2021.08.14',
  posterTextPlaceholderCustom: 'Egy rövid személyes üzenet',
  objectsForCity: 'Objektumok a térképen',
  starTextOnly: 'Csillagtérkép esetén csak szöveges testreszabás érhető el.',
  reviewLocation: 'Helyszín',
  reviewStyle: 'Stílus',
  reviewFrame: 'Keret',
  reviewPrice: 'Ár',
  showMap: 'Mutasd a térképet',
  showMapLoading: 'Térkép készítése...',
  updatePreview: 'Térkép generálása',
  stylePreviewNoticeTitle: 'ELŐNÉZET',
  stylePreviewNoticeBodyLine1: 'A megjelenített stílusok és színpaletták illusztrációk.',
  stylePreviewNoticeBodyLine2: 'A végleges térképet a rendszer a „Mutasd a térképet” gomb megnyomásakor készíti el a kiválasztott helyszín alapján.',
  previewToolbarLocation: 'Helyszín',
  previewToolbarStyle: 'Stílus',
  previewToolbarStyleValue: (moduleKind: string) => moduleKind === 'star-map' ? 'Csillagtérkép - Klasszikus' : 'Várostérkép - Minimál',
  share: 'Megosztás',
  defaultPosterTitle: 'BUDAPEST',
  defaultPosterSubtitle: 'MAGYARORSZÁG',
  previewHelpPlacement: 'Kattints az alkotásra és helyezd el a jelölőket.',
  size: 'Méret',
  paper: 'Papír',
  price: 'Ár',
  addToCart: 'Kosárba',
  premiumMatte: 'Prémium matt',
  sizeDefault: '50x50 cm',
  locationNotSelected: 'Nincs kiválasztva',
  nextStepHint: 'Folytasd a következő lépéssel a tökéletes poszterhez.',
  summaryCardKicker: 'A te posztered',
  donePrefix: '✓',
  summaryTitleSet: 'Cím beállítva',
  summaryDateSet: 'Dátum beállítva',
  summarySubtitleSet: 'Alcím beállítva',
  summaryCustomSet: 'Egyedi szöveg beállítva',
  summaryTypography: (style: 'urban' | 'nordic' | 'classic') => {
    if (style === 'urban') {
      return 'Urban tipográfia'
    }
    if (style === 'nordic') {
      return 'Nordic tipográfia'
    }
    return 'Classic tipográfia'
  },
  summaryObjects: (count: number) => `${count} objektum`,
  summaryLabels: (count: number) => `${count} felirat`,
  summaryStyleFallback: 'Nincs kiválasztva',
  summaryFrameSuffix: 'keret',
  summaryNotConfigured: 'Még nincs beállítva',
  previewStatusLoading: 'Előnézet frissítése folyamatban',
  renderInProgressTitle: 'A térképet most készítjük.',
  renderInProgressHint: 'Ez akár több percig eltarthat.',
  previewStatusFailed: 'Az előnézet frissítése nem sikerült',
  previewStatusCityNotFound: 'A város nem található',
  mockLabels: {
    firstDate: 'Első randi',
    firstHome: 'Első közös otthon',
    proposal: 'Lánykérés',
    mainEntrance: 'Főbejárat',
    skylineFocus: 'Panoráma fókusz',
    birthdayStar: 'Születésnapi csillag',
    anniversaryNight: 'Évfordulós este',
  },
} as const

export const toHuLabel = (value: string, mapping: Record<string, string>): string => {
  return mapping[value] ?? value
}

export const toHuPreviewError = (error: string | null): string => {
  if (!error) {
    return huUiText.previewGenerationFailed
  }

  if (error === 'City Not Found') {
    return huUiText.cityNotFound
  }
  if (error === 'Preview Generation Failed') {
    return huUiText.previewGenerationFailed
  }
  if (error === 'Enter a city name first.') {
    return huUiText.enterCityFirst
  }
  if (error === huUiText.enterCityFirst) {
    return huUiText.enterCityFirst
  }

  return huUiText.unknownPreviewError
}
