import { useId } from 'react'

/** Local decorative artwork; it conveys no readiness or execution state. */
export function NovaOrbit({ className = '' }: { className?: string }) {
  const prefix = `nova-orbit-${useId().replace(/:/g, '')}`
  const gradient = (name: string) => `url(#${prefix}-${name})`
  return (
    <div className={`nova-orbit ${className}`.trim()} aria-hidden="true">
      <svg viewBox="0 0 860 640" fill="none" focusable="false">
        <defs>
          <radialGradient id={`${prefix}-halo`}>
            <stop stopColor="#ffad00" stopOpacity=".2" />
            <stop offset=".44" stopColor="#ef9200" stopOpacity=".07" />
            <stop offset="1" stopColor="#d88000" stopOpacity="0" />
          </radialGradient>
          <linearGradient id={`${prefix}-gold`} x1="370" y1="220" x2="480" y2="375" gradientUnits="userSpaceOnUse">
            <stop stopColor="#ffe174" />
            <stop offset=".27" stopColor="#ffc523" />
            <stop offset=".65" stopColor="#ee9e00" />
            <stop offset="1" stopColor="#ffc537" />
          </linearGradient>
          <linearGradient id={`${prefix}-line`} x1="290" y1="180" x2="565" y2="440" gradientUnits="userSpaceOnUse">
            <stop stopColor="#b77100" stopOpacity=".24" />
            <stop offset=".35" stopColor="#ffcc36" />
            <stop offset=".73" stopColor="#dd9500" stopOpacity=".55" />
            <stop offset="1" stopColor="#ffd74a" stopOpacity=".9" />
          </linearGradient>
          <radialGradient id={`${prefix}-floor`}>
            <stop stopColor="#ffbe21" stopOpacity=".56" />
            <stop offset=".25" stopColor="#dc8700" stopOpacity=".18" />
            <stop offset="1" stopColor="#d57b00" stopOpacity="0" />
          </radialGradient>
          <filter id={`${prefix}-soft`} x="-100%" y="-100%" width="300%" height="300%">
            <feGaussianBlur stdDeviation="13" />
          </filter>
          <filter id={`${prefix}-bloom`} x="-100%" y="-100%" width="300%" height="300%">
            <feGaussianBlur stdDeviation="3" />
          </filter>
        </defs>
        <ellipse className="nova-orbit-halo" cx="430" cy="303" rx="318" ry="280" fill={gradient('halo')} />
        <g className="nova-orbit-distant" opacity=".36" stroke="#ae6900" strokeWidth=".65">
          <ellipse cx="430" cy="165" rx="375" ry="187" transform="rotate(-23 430 165)" />
          <ellipse cx="468" cy="204" rx="413" ry="220" transform="rotate(-35 468 204)" opacity=".37" />
        </g>
        <g className="nova-orbit-floor">
          <ellipse cx="430" cy="487" rx="196" ry="41" fill={gradient('floor')} opacity=".8" />
          <path d="M270 482h320" stroke="#f4a500" strokeOpacity=".25" />
          <ellipse cx="430" cy="480" rx="43" ry="3" fill="#ffb719" opacity=".65" filter={gradient('bloom')} />
        </g>
        <g className="nova-orbit-core">
          <g className="nova-orbit-glow">
            <circle cx="430" cy="301" r="77" stroke="#ffb900" strokeWidth="34" opacity=".24" filter={gradient('soft')} />
          </g>
          <g className="nova-orbit-rings">
            <ellipse cx="430" cy="302" rx="133" ry="151" stroke={gradient('line')} strokeWidth=".8" transform="rotate(-24 430 302)" opacity=".75" />
            <ellipse cx="430" cy="302" rx="151" ry="113" stroke={gradient('line')} strokeWidth="1.15" transform="rotate(31 430 302)" />
            <ellipse cx="430" cy="302" rx="122" ry="143" stroke={gradient('line')} strokeWidth=".85" transform="rotate(64 430 302)" opacity=".8" />
            <ellipse cx="430" cy="302" rx="139" ry="132" stroke="#ecaa17" strokeWidth=".5" transform="rotate(10 430 302)" opacity=".4" />
          </g>
          <g className="nova-orbit-nucleus">
            <circle cx="430" cy="301" r="64" stroke={gradient('gold')} strokeWidth="36" />
            <circle cx="430" cy="301" r="82" stroke="#ffe47c" strokeOpacity=".84" strokeWidth=".9" />
            <circle cx="430" cy="301" r="46" stroke="#ffcf4e" strokeOpacity=".76" strokeWidth=".9" />
          </g>
          <g className="nova-orbit-satellite nova-orbit-satellite-a">
            <circle cx="298" cy="238" r="8.5" fill="#ffc126" />
            <circle cx="298" cy="238" r="11" fill="#ffb900" opacity=".2" filter={gradient('bloom')} />
          </g>
          <g className="nova-orbit-satellite nova-orbit-satellite-b">
            <circle cx="330" cy="392" r="7.5" fill="#ffc126" />
            <circle cx="330" cy="392" r="10" fill="#ffb900" opacity=".18" filter={gradient('bloom')} />
          </g>
        </g>
        <g className="nova-orbit-sparks" fill="#ffc02c">
          <circle cx="140" cy="370" r="1.7" />
          <circle cx="677" cy="240" r="1.7" />
          <circle cx="196" cy="130" r="1.15" opacity=".65" />
          <circle cx="606" cy="398" r="1.3" opacity=".7" />
          <circle cx="737" cy="364" r=".8" opacity=".6" />
          <circle cx="268" cy="433" r="1" opacity=".75" />
          <circle cx="556" cy="139" r=".8" opacity=".5" />
        </g>
      </svg>
    </div>
  )
}
