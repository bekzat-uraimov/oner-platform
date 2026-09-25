/**
 * A course's cover, or, when it has none, a poster in the same style as the
 * made covers: dark, gridded, the category in big type with a lime dot.
 * Sizes use container units, so it reads the same as a thumbnail or a hero.
 */
export function CourseArt({
  title,
  cover,
  segment,
  className = "",
}: {
  title: string;
  cover?: string | null;
  segment?: string | null;
  className?: string;
}) {
  if (cover) {
    // Covers are arbitrary URLs set by an admin, so next/image can't know their hosts.
    // eslint-disable-next-line @next/next/no-img-element
    return <img src={cover} alt="" className={`object-cover ${className}`} />;
  }
  const word = segment?.trim() || title.split(/\s+/)[0];
  return (
    <div aria-hidden className={`overflow-hidden bg-[#0a0a0b] [container-type:inline-size] ${className}`}>
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_70%_40%,rgba(181,242,61,.22),transparent_62%)]" />
      <div className="poster-grid absolute inset-0" />
      <span className="absolute left-[6%] top-[11%] font-mono text-[2.2cqw] uppercase tracking-[0.3em] text-[#b5f23d]">ONER</span>
      <span className="absolute inset-x-[5.5%] bottom-[7%] truncate text-[12cqw] font-bold leading-none tracking-[-0.05em] text-white">
        {word}
        <span className="text-[#b5f23d]">.</span>
      </span>
      <div className="art-grain absolute inset-0" />
    </div>
  );
}
