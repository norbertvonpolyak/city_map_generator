import type { UMCModuleKind } from '@umc-shared/types'

interface ModuleMockMapLayerProps {
  moduleKind: UMCModuleKind
}

export const ModuleMockMapLayer = ({ moduleKind }: ModuleMockMapLayerProps) => {
  if (moduleKind === 'city-map') {
    return (
      <svg viewBox="0 0 1000 1000" className="absolute inset-0 h-full w-full" aria-hidden="true">
        <defs>
          <linearGradient id="cityWater" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor="rgba(126,235,226,0.28)" />
            <stop offset="100%" stopColor="rgba(126,235,226,0.08)" />
          </linearGradient>
          <linearGradient id="cityRoad" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" stopColor="rgba(233,226,212,0.34)" />
            <stop offset="100%" stopColor="rgba(233,226,212,0.1)" />
          </linearGradient>
        </defs>
        <rect x="0" y="0" width="1000" height="1000" fill="rgba(7,11,16,0.36)" />
        <path
          d="M170 720 C 300 520, 420 560, 590 390 C 700 280, 780 310, 850 250"
          fill="none"
          stroke="url(#cityWater)"
          strokeWidth="70"
          strokeLinecap="round"
        />
        <path
          d="M120 580 C 250 620, 350 500, 470 530 C 610 560, 690 470, 820 510"
          fill="none"
          stroke="url(#cityRoad)"
          strokeWidth="20"
          strokeLinecap="round"
        />
        <path
          d="M180 320 C 350 390, 440 350, 560 250 C 680 150, 760 190, 860 130"
          fill="none"
          stroke="rgba(201,171,120,0.34)"
          strokeWidth="14"
          strokeLinecap="round"
        />
        <g fill="none" stroke="rgba(233,226,212,0.15)" strokeWidth="1.5">
          <path d="M220 210 L820 210" />
          <path d="M220 310 L820 310" />
          <path d="M220 410 L820 410" />
          <path d="M220 510 L820 510" />
          <path d="M220 610 L820 610" />
          <path d="M220 710 L820 710" />
          <path d="M220 210 L220 770" />
          <path d="M340 210 L340 770" />
          <path d="M460 210 L460 770" />
          <path d="M580 210 L580 770" />
          <path d="M700 210 L700 770" />
          <path d="M820 210 L820 770" />
        </g>
      </svg>
    )
  }

  if (moduleKind === 'building-map') {
    return (
      <svg viewBox="0 0 1000 1000" className="absolute inset-0 h-full w-full" aria-hidden="true">
        <defs>
          <linearGradient id="buildGlow" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="rgba(201,171,120,0.28)" />
            <stop offset="100%" stopColor="rgba(201,171,120,0.08)" />
          </linearGradient>
        </defs>
        <rect x="0" y="0" width="1000" height="1000" fill="rgba(8,10,14,0.42)" />
        <path d="M120 760 L880 760" stroke="rgba(233,226,212,0.26)" strokeWidth="3" />
        <g fill="rgba(11,14,20,0.8)" stroke="url(#buildGlow)" strokeWidth="3">
          <rect x="180" y="460" width="130" height="300" rx="8" />
          <rect x="320" y="380" width="130" height="380" rx="8" />
          <rect x="460" y="300" width="130" height="460" rx="8" />
          <rect x="600" y="360" width="130" height="400" rx="8" />
          <rect x="740" y="430" width="90" height="330" rx="8" />
        </g>
        <g stroke="rgba(126,235,226,0.2)" strokeWidth="1">
          <path d="M180 520 L310 520" />
          <path d="M320 460 L450 460" />
          <path d="M460 420 L590 420" />
          <path d="M600 470 L730 470" />
          <path d="M180 580 L830 580" />
          <path d="M180 640 L830 640" />
        </g>
        <g fill="rgba(233,226,212,0.34)">
          <circle cx="245" cy="530" r="3" />
          <circle cx="390" cy="470" r="3" />
          <circle cx="530" cy="430" r="3" />
          <circle cx="665" cy="480" r="3" />
        </g>
      </svg>
    )
  }

  return (
    <svg viewBox="0 0 1000 1000" className="absolute inset-0 h-full w-full" aria-hidden="true">
      <defs>
        <linearGradient id="neutralGlow" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="rgba(201,171,120,0.20)" />
          <stop offset="100%" stopColor="rgba(126,235,226,0.08)" />
        </linearGradient>
      </defs>
      <rect x="0" y="0" width="1000" height="1000" fill="rgba(5,8,13,0.55)" />
      <circle cx="500" cy="500" r="360" fill="url(#neutralGlow)" />
      <g fill="none" stroke="rgba(233,226,212,0.18)" strokeWidth="2">
        <path d="M160 280 L320 250 L470 320 L610 270 L780 320" />
        <path d="M210 610 L360 560 L520 590 L680 540 L820 590" />
        <path d="M240 180 L240 820" />
        <path d="M420 150 L420 850" />
        <path d="M620 170 L620 830" />
      </g>
      <g fill="rgba(233,226,212,0.42)">
        <circle cx="180" cy="300" r="3" />
        <circle cx="310" cy="260" r="2.5" />
        <circle cx="430" cy="330" r="3" />
        <circle cx="560" cy="280" r="2.5" />
        <circle cx="690" cy="340" r="3" />
        <circle cx="820" cy="290" r="2.5" />
      </g>
    </svg>
  )
}