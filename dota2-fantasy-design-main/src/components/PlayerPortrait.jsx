import { portraitAsset } from '../data/assets.js';

/**
 * PlayerPortrait — 1024×1024 transparent cutouts, cropped to head-and-chest
 * and bled off the bottom edge of the banner exactly as the client does.
 *
 * `parallax` shifts the portrait against its frame on hover. Depth comes from
 * a token so reduced-motion can zero it globally.
 */
export default function PlayerPortrait({
  teamDir,
  name,
  height = 150,
  parallax = 0,
  className = '',
  grayscale = false,
  eager = false,        // true for the banner's own portraits — above the fold
}) {
  const url = portraitAsset(teamDir, name);

  if (!url) {
    return (
      <div
        className={`grid place-items-end justify-center ${className}`}
        style={{ height }}
        aria-hidden="true"
      >
        <span className="label-caps text-onparch-tertiary pb-2">{name}</span>
      </div>
    );
  }

  return (
    <div className={`relative overflow-hidden ${className}`} style={{ height }}>
      <img
        src={url}
        alt={`${name} portrait`}
        loading={eager ? 'eager' : 'lazy'}
        draggable={false}
        className="absolute left-1/2 bottom-0 w-auto max-w-none transition-transform duration-slow ease-settle"
        style={{
          /* 1.14×, not 1.42×. The source is a 1024² cutout with the crown of
             the head at roughly 8% from the top; at 1.42× bottom-aligned we
             clipped the top 29% and cut straight through the forehead. */
          height: height * 1.14,
          transform: `translateX(-50%) translateY(${parallax}px)`,
          objectFit: 'contain',
          filter: grayscale ? 'grayscale(0.85) brightness(0.8)' : 'none',
        }}
      />
    </div>
  );
}
