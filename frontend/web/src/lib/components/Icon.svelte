<script lang="ts" module>
  /** Line icons (24 × 24, stroke = currentColor). Static markup only — never user input. */
  const PATHS = {
    grid: '<rect x="3.5" y="3.5" width="7" height="7" rx="2"/><rect x="13.5" y="3.5" width="7" height="7" rx="2"/><rect x="3.5" y="13.5" width="7" height="7" rx="2"/><rect x="13.5" y="13.5" width="7" height="7" rx="2"/>',
    check: '<circle cx="12" cy="12" r="8.5"/><path d="m8.5 12.3 2.4 2.4 4.6-4.9"/>',
    trophy: '<path d="M7.5 4h9v5a4.5 4.5 0 0 1-9 0V4Z"/><path d="M16.5 6h2.5a1 1 0 0 1 1 1v1a3.5 3.5 0 0 1-3.6 3.5"/><path d="M7.5 6H5a1 1 0 0 0-1 1v1a3.5 3.5 0 0 0 3.6 3.5"/><path d="M12 13.5V17"/><path d="M8.5 20h7"/><path d="M10 17h4"/>',
    chart: '<path d="M4 4v16h16"/><path d="m7.5 14.5 3.5-3.5 3 3 5-5.5"/>',
    heart: '<path d="M12 19.5s-7.5-4.4-7.5-10A4.2 4.2 0 0 1 12 7a4.2 4.2 0 0 1 7.5 2.5c0 5.6-7.5 10-7.5 10Z"/>',
    users: '<circle cx="9" cy="8.5" r="3.5"/><path d="M2.5 19.5a6.5 6.5 0 0 1 13 0"/><path d="M16 5.1a3.5 3.5 0 0 1 0 6.8"/><path d="M18.2 14a6.5 6.5 0 0 1 3.3 5.5"/>',
    'user-cog': '<circle cx="10" cy="8" r="3.8"/><path d="M3.5 19.5a6.6 6.6 0 0 1 9.6-5.8"/><circle cx="18" cy="17" r="2.3"/><path d="M18 12.9v1.8M18 19.3v1.8M13.9 17h1.8M20.3 17h1.8"/>',
    building: '<rect x="4.5" y="3.5" width="15" height="17" rx="2"/><path d="M9 7.5h1.5M13.5 7.5H15M9 11.5h1.5M13.5 11.5H15M9 15.5h1.5M13.5 15.5H15"/>',
    award: '<circle cx="12" cy="9" r="5.5"/><path d="M8.7 13.4 7.5 20.5l4.5-2.4 4.5 2.4-1.2-7.1"/>',
    globe: '<circle cx="12" cy="12" r="8.5"/><path d="M3.5 12h17"/><path d="M12 3.5c2.3 2.3 3.4 5.2 3.4 8.5s-1.1 6.2-3.4 8.5c-2.3-2.3-3.4-5.2-3.4-8.5S9.7 5.8 12 3.5Z"/>',
    bell: '<path d="M6.2 9.5a5.8 5.8 0 0 1 11.6 0c0 5.5 2.2 7 2.2 7H4s2.2-1.5 2.2-7Z"/><path d="M10 19.5a2.1 2.1 0 0 0 4 0"/>',
    user: '<circle cx="12" cy="8" r="4"/><path d="M4.5 20.5a7.5 7.5 0 0 1 15 0"/>',
    menu: '<path d="M4 7h16M4 12h16M4 17h10"/>',
    sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2.8v1.9M12 19.3v1.9M4.9 4.9l1.3 1.3M17.8 17.8l1.3 1.3M2.8 12h1.9M19.3 12h1.9M4.9 19.1l1.3-1.3M17.8 6.2l1.3-1.3"/>',
    moon: '<path d="M19.5 14.6A7.8 7.8 0 0 1 9.4 4.5a7.8 7.8 0 1 0 10.1 10.1Z"/>',
    monitor: '<rect x="3" y="4.5" width="18" height="12" rx="2.2"/><path d="M8.5 20h7M12 16.5V20"/>',
    'chevron-down': '<path d="m6.5 9.5 5.5 5.5 5.5-5.5"/>',
    logout: '<path d="M14.5 4.5H18a2 2 0 0 1 2 2v11a2 2 0 0 1-2 2h-3.5"/><path d="m9.5 16.5-4.5-4.5 4.5-4.5"/><path d="M5 12h10.5"/>',
    search: '<circle cx="11" cy="11" r="6.5"/><path d="m20 20-4.2-4.2"/>',
    close: '<path d="M6.5 6.5l11 11M17.5 6.5l-11 11"/>',
    calendar: '<rect x="3.5" y="5" width="17" height="15.5" rx="2.5"/><path d="M3.5 10h17M8 3v4M16 3v4"/>',
    shield: '<path d="M12 3.5 5.5 6v5c0 4.2 2.8 7.8 6.5 9.5 3.7-1.7 6.5-5.3 6.5-9.5V6L12 3.5Z"/><path d="m9.3 12.2 1.9 1.9 3.6-3.8"/>',
  } as const;

  export type IconName = keyof typeof PATHS;

  /** Sidebar route → icon. Routes not listed fall back to the nav item's own emoji. */
  export const NAV_ICONS: Readonly<Record<string, IconName>> = {
    '/dashboard': 'grid',
    '/habits': 'check',
    '/challenges': 'trophy',
    '/analytics': 'chart',
    '/habits/team': 'heart',
    '/team': 'users',
    '/admin/users': 'user-cog',
    '/admin/teams': 'building',
    '/admin/badge-rules': 'award',
    '/admin/insights': 'globe',
    '/notifications': 'bell',
    '/profile': 'user',
  };
</script>

<script lang="ts">
  interface Props {
    name: IconName;
    size?: number;
    strokeWidth?: number;
  }

  let { name, size = 20, strokeWidth = 1.8 }: Props = $props();
</script>

<svg
  class="icon"
  viewBox="0 0 24 24"
  width={size}
  height={size}
  fill="none"
  stroke="currentColor"
  stroke-width={strokeWidth}
  stroke-linecap="round"
  stroke-linejoin="round"
  aria-hidden="true"
  focusable="false"
>
  {@html PATHS[name]}
</svg>

<style>
  .icon {
    flex: none;
    display: block;
  }
</style>
