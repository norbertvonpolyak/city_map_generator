export interface UMCProductTypeOption {
  id: 'city-map' | 'star-map'
  label: string
}

export interface UMCFrameOption {
  id: 'none' | 'wood-brown' | 'black' | 'white'
  label: string
}

export interface UMCSizeOption {
  id: string
  label: string
  widthCm: number
  heightCm: number
}

export interface UMCPaperOption {
  id: 'premium-matte'
  label: string
}

export interface UMCPriceOption {
  productTypeId: UMCProductTypeOption['id']
  frameId: UMCFrameOption['id']
  sizeId: string
  paperId: UMCPaperOption['id']
  amountHuf: number
}

export const umcProductTypes: UMCProductTypeOption[] = [
  { id: 'city-map', label: 'Várostérkép' },
  { id: 'star-map', label: 'Csillagtérkép' },
]

export const umcFrameOptions: UMCFrameOption[] = [
  { id: 'none', label: 'Keret nélkül' },
  { id: 'wood-brown', label: 'Fa, barna' },
  { id: 'black', label: 'Fekete' },
  { id: 'white', label: 'Fehér' },
]

export const umcSizeOptions: UMCSizeOption[] = [
  { id: '40x50', label: '40 × 50 cm', widthCm: 40, heightCm: 50 },
  { id: '50x40', label: '50 × 40 cm', widthCm: 50, heightCm: 40 },
  { id: '50x50', label: '50 × 50 cm', widthCm: 50, heightCm: 50 },
  { id: '50x70', label: '50 × 70 cm', widthCm: 50, heightCm: 70 },
  { id: '70x50', label: '70 × 50 cm', widthCm: 70, heightCm: 50 },
  { id: '60x90', label: '60 × 90 cm', widthCm: 60, heightCm: 90 },
  { id: '90x60', label: '90 × 60 cm', widthCm: 90, heightCm: 60 },
]

export const umcPaperOptions: UMCPaperOption[] = [
  { id: 'premium-matte', label: 'Prémium matt' },
]

export const umcPriceMatrix: UMCPriceOption[] = [
  {
    productTypeId: 'city-map',
    frameId: 'wood-brown',
    sizeId: '50x50',
    paperId: 'premium-matte',
    amountHuf: 9990,
  },
  {
    productTypeId: 'star-map',
    frameId: 'wood-brown',
    sizeId: '50x50',
    paperId: 'premium-matte',
    amountHuf: 9990,
  },
]

export const resolveUmcPrice = (
  productTypeId: UMCProductTypeOption['id'],
  frameId: UMCFrameOption['id'],
  sizeId: UMCSizeOption['id'],
  paperId: UMCPaperOption['id'],
): number => {
  const match = umcPriceMatrix.find((item) => {
    return item.productTypeId === productTypeId
      && item.frameId === frameId
      && item.sizeId === sizeId
      && item.paperId === paperId
  })

  return match?.amountHuf ?? 9990
}
