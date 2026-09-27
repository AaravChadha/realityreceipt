// Two pages, told apart by the URL hash (PLAN.md tasks 2.8 and 4.4.1): "#/shop" is the shop,
// anything else is the entry form. A hash needs no router package and no server rewrite rule,
// and a link to it works from a phone through the tunnel.
import { BadgeCheck, ReceiptText, Refrigerator, ShoppingBag, type LucideIcon } from 'lucide-react'
import { useEffect, useState } from 'react'
import { cn } from '@/lib/utils'
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

function NavLink({ href, current, icon: Icon, children }: { href: string; current: boolean; icon: LucideIcon; children: string }) {
  return (
    <a
      href={href}
      aria-current={current ? 'page' : undefined}
      className={cn(
        'inline-flex min-h-11 flex-1 items-center justify-center gap-2 rounded-lg px-3 text-sm font-semibold transition-colors outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50',
        current ? 'bg-card text-foreground shadow-sm' : 'text-muted-foreground hover:text-foreground',
      )}
    >
      <Icon aria-hidden="true" className="size-4" />
      {children}
    </a>
  )
}

export default function App() {
  const onShop = useOnShopPage()
  return (
    <div
      className={cn(
        'mx-auto flex min-h-svh w-full max-w-md flex-col px-4 pt-5 pb-10 sm:px-6',
        // Entry sits form beside receipt on wide screens; Shop stays one comfortable column.
        onShop ? 'lg:max-w-2xl' : 'lg:max-w-5xl',
      )}
    >
      <header className="mb-6 lg:max-w-2xl">
        <div className="flex items-center gap-2.5">
          <span aria-hidden="true" className="grid size-10 place-items-center rounded-xl bg-primary text-primary-foreground shadow-sm">
            <ReceiptText className="size-5" />
          </span>
          <h1 className="text-2xl font-bold tracking-tight">
            Reality<span className="text-primary">Receipt</span>
          </h1>
        </div>
        <p className="mt-3 text-pretty text-muted-foreground">
          Every way to get a fridge, side by side: what you pay today, over 3 years, and per year of use.
        </p>
        <nav aria-label="Pages" className="mt-4 flex gap-1 rounded-xl border border-border bg-muted p-1">
          <NavLink href="#/" current={!onShop} icon={Refrigerator}>
            Check a fridge
          </NavLink>
          <NavLink href={SHOP_HASH} current={onShop} icon={ShoppingBag}>
            Shop for one
          </NavLink>
        </nav>
      </header>
      <main className="flex-1">{onShop ? <Shop /> : <Entry />}</main>
      <footer className="mt-10 flex items-center justify-center gap-1.5 text-xs text-muted-foreground">
        <BadgeCheck aria-hidden="true" className="size-3.5" />
        Every number opens to its source.
      </footer>
    </div>
  )
}
