import { render, screen } from '@testing-library/react'

import { App } from './App'

test('renders the plan-review heading', () => {
  render(<App />)

  expect(screen.getByRole('heading', { name: 'plan-review' })).toBeInTheDocument()
})
