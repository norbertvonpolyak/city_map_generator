export interface UMCProductTypeOption {
  id: 'city-map' | 'star-map'
  label: string
}

export interface UMCFrameOption {
  id: 'none' | 'wood-brown' | 'black' | 'white'
  label: string
}

export interface UMCSizeOption {
  id: '50x50'
  label: string
}

export interface UMCPaperOption {
  id: 'premium-matte'
  label: string
}

export interface UMCPriceOption {
  productTypeId: UMCProductTypeOption['id']
  frameId: UMCFrameOption['id']
  sizeId: UMCSizeOption['id']
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
  { id: '50x50', label: '50x50 cm' },
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
