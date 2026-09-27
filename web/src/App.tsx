// Two pages, told apart by the URL hash (PLAN.md tasks 2.8 and 4.4.1): "#/shop" is the shop,
// anything else is the entry form. A hash needs no router package and no server rewrite rule,
// and a link to it works from a phone through the tunnel.
import { useEffect, useState } from 'react'
import Entry from './pages/Entry'
import Shop from './pages/Shop'

const SHOP_HASH = '#/shop'

function useOnShopPage(): boolean {
  const [onShop, setOnShop] = useState(() => window.location.hash === SHOP_HASH)
  useEffect(() => {
    const sync = () => setOnShop(window.location.hash === SHOP_HASH)
    window.addEventListener('hashchange', sync)
    sync()
    return () => window.removeEventListener('hashchange', sync)
  }, [])
  return onShop
}

function NavLink({ href, current, children }: { href: string; current: boolean; children: string }) {
  return (
    <a
      href={href}
      aria-current={current ? 'page' : undefined}
      className={`inline-flex min-h-11 items-center rounded-full border px-4 text-sm font-medium focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-700 ${
        current
          ? 'border-emerald-700 bg-emerald-700 text-white'
          : 'border-stone-300 bg-white text-stone-800 hover:bg-stone-50 dark:border-stone-700 dark:bg-stone-900 dark:text-stone-200 dark:hover:bg-stone-800'
      }`}
    >
      {children}
    </a>
  )
}

export default function App() {
  const onShop = useOnShopPage()
  return (
    <div className="mx-auto min-h-svh w-full max-w-md px-4 pt-6 pb-12">
      <header className="mb-6">
        <h1 className="text-2xl font-semibold tracking-tight">RealityReceipt</h1>
        <p className="mt-1 text-stone-600 dark:text-stone-400">
          Every way to get a fridge, side by side: what you pay today, over 3 years, and per year of use.
        </p>
        <nav aria-label="Pages" className="mt-4 flex flex-wrap gap-2">
          <NavLink href="#/" current={!onShop}>
            Check a fridge
          </NavLink>
          <NavLink href={SHOP_HASH} current={onShop}>
            Shop for one
          </NavLink>
        </nav>
      </header>
      <main>{onShop ? <Shop /> : <Entry />}</main>
    </div>
  )
}
