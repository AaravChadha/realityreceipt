import Entry from './pages/Entry'

export default function App() {
  return (
    <div className="mx-auto min-h-svh w-full max-w-md px-4 pt-6 pb-12">
      <header className="mb-6">
        <h1 className="text-2xl font-semibold tracking-tight">RealityReceipt</h1>
        <p className="mt-1 text-stone-600 dark:text-stone-400">
          Every way to get a fridge, side by side: what you pay today, over 3 years, and per year of use.
        </p>
      </header>
      <main>
        <Entry />
      </main>
    </div>
  )
}
