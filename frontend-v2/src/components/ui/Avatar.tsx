import clsx from 'clsx';
import { initials } from '../../lib/format';

const PALETTE = [
  'bg-indigo-50 text-indigo-700',
  'bg-teal-50 text-teal-700',
  'bg-amber-50 text-amber-800',
  'bg-rose-50 text-rose-700',
  'bg-sky-50 text-sky-700',
  'bg-emerald-50 text-emerald-700',
];

function paletteFor(seed: string) {
  let hash = 0;
  for (let i = 0; i < seed.length; i += 1) hash = (hash * 31 + seed.charCodeAt(i)) >>> 0;
  return PALETTE[hash % PALETTE.length];
}

export function Avatar({ name, size = 'md' }: { name: string; size?: 'sm' | 'md' | 'lg' }) {
  return (
    <span
      className={clsx(
        'inline-flex shrink-0 items-center justify-center rounded-full font-semibold',
        size === 'sm' ? 'h-6 w-6 text-[10px]' : size === 'lg' ? 'h-12 w-12 text-[16px]' : 'h-8 w-8 text-[12px]',
        paletteFor(name),
      )}
    >
      {initials(name)}
    </span>
  );
}
