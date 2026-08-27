import { useEffect, useRef, useCallback } from 'react';
import './RotateMark.css';

/**
 * RotateMark — Original radial ray-burst brand mark.
 *
 * Props:
 *   size       {number}  Width/height in px. Default: 40
 *   color      {string}  Optional solid color override (replaces gradient).
 *   className  {string}  Additional CSS class names.
 *   isLoading  {boolean} Forces the spinning animation (takes priority over hover/tilt).
 */
function RotateMark({ size = 40, color, className = '', isLoading = false }) {
  const containerRef = useRef(null);
  const isSpinningRef = useRef(false);
  const currentTiltRef = useRef(0);
  const targetTiltRef = useRef(0);
  const rafRef = useRef(null);

  // Unique gradient ID per instance (avoids SVG gradient collisions)
  const gradientId = useRef(`rmg-${Math.random().toString(36).slice(2, 9)}`);

  // ─── Ray geometry ─────────────────────────────────────────
  const cx = size / 2;
  const cy = size / 2;
  const rayCount = 16;
  const innerR = size * 0.22;
  const outerR = size * 0.46;
  const rayW = size * 0.055;
  const rayRx = rayW / 2;

  // ─── Continuous smooth physics-based lerp loop ────────────
  useEffect(() => {
    let active = true;

    const loop = () => {
      if (!active) return;

      if (containerRef.current) {
        // If spinning, gently ease tilt to 0; otherwise lerp toward targetTilt
        const target = isSpinningRef.current ? 0 : targetTiltRef.current;
        // Smooth interpolation factor (0.1 = buttery smooth spring lag)
        currentTiltRef.current += (target - currentTiltRef.current) * 0.12;

        // Apply only if difference is noticeable to save GPU cycles
        if (Math.abs(target - currentTiltRef.current) > 0.01) {
          containerRef.current.style.transform = `rotate(${currentTiltRef.current.toFixed(2)}deg)`;
        }
      }

      rafRef.current = requestAnimationFrame(loop);
    };

    rafRef.current = requestAnimationFrame(loop);

    return () => {
      active = false;
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
    };
  }, []);

  // ─── Behavior 1: Ambient pointer tracking ─────────────────
  const onMouseMove = useCallback((e) => {
    if (!containerRef.current || isSpinningRef.current) return;
    const rect = containerRef.current.getBoundingClientRect();
    const elCx = rect.left + rect.width / 2;
    const elCy = rect.top + rect.height / 2;
    const dx = e.clientX - elCx;
    const dy = e.clientY - elCy;
    const rawAngle = Math.atan2(dy, dx) * (180 / Math.PI);
    // Smoothly scale down to gentle lean: ±18° max
    targetTiltRef.current = Math.max(-18, Math.min(18, rawAngle * 0.08));
  }, []);

  // ─── Behavior 2: Direct hover spin ────────────────────────
  const onMouseEnter = useCallback(() => {
    if (isLoading) return;
    isSpinningRef.current = true;
    if (containerRef.current) {
      containerRef.current.classList.add('spinning');
    }
  }, [isLoading]);

  const onMouseLeave = useCallback(() => {
    if (isLoading) return;
    isSpinningRef.current = false;
    if (containerRef.current) {
      containerRef.current.classList.remove('spinning');
    }
  }, [isLoading]);

  // ─── isLoading override ────────────────────────────────────
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;

    if (isLoading) {
      isSpinningRef.current = true;
      el.classList.add('spinning');
    } else {
      isSpinningRef.current = false;
      el.classList.remove('spinning');
    }
  }, [isLoading]);

  // ─── Attach global listener ───────────────────────────────
  useEffect(() => {
    window.addEventListener('mousemove', onMouseMove, { passive: true });
    return () => {
      window.removeEventListener('mousemove', onMouseMove);
    };
  }, [onMouseMove]);

  return (
    <span
      ref={containerRef}
      className={`rotate-mark-container ${className}`}
      style={{
        width: size,
        height: size,
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        flexShrink: 0,
      }}
      onMouseEnter={onMouseEnter}
      onMouseLeave={onMouseLeave}
    >
      <svg
        className="rotate-mark-svg"
        width={size}
        height={size}
        viewBox={`0 0 ${size} ${size}`}
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        aria-hidden="true"
      >
        <defs>
          <linearGradient
            id={gradientId.current}
            x1="0%" y1="0%" x2="100%" y2="100%"
          >
            <stop offset="0%" stopColor={color || 'var(--mark-color-a)'} />
            <stop offset="100%" stopColor={color || 'var(--mark-color-b)'} />
          </linearGradient>
        </defs>

        {/* 16 rays, evenly spaced at 22.5° intervals */}
        {Array.from({ length: rayCount }, (_, i) => {
          const angle = i * (360 / rayCount);
          return (
            <rect
              key={i}
              x={cx - rayW / 2}
              y={cy - outerR}
              width={rayW}
              height={outerR - innerR}
              rx={rayRx}
              ry={rayRx}
              fill={`url(#${gradientId.current})`}
              transform={`rotate(${angle}, ${cx}, ${cy})`}
            />
          );
        })}
      </svg>
    </span>
  );
}

export default RotateMark;
