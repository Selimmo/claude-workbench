import { fireEvent, render, screen } from '@testing-library/react'

import { ThemeSwitch } from './ThemeSwitch'
import { STORAGE_KEY, applyStoredTheme } from './theme'

const root = document.documentElement

afterEach(() => {
  localStorage.clear()
  delete root.dataset.theme
})

test('defaults to Auto, which leaves the colour scheme to the OS', () => {
  render(<ThemeSwitch />)

  expect(screen.getByRole('radio', { name: 'Auto' })).toBeChecked()
  expect(root.dataset.theme).toBeUndefined()
})

test('choosing a theme applies it and remembers it; Auto clears it', () => {
  render(<ThemeSwitch />)

  fireEvent.click(screen.getByRole('radio', { name: 'Dark' }))
  expect(root.dataset.theme).toBe('dark')
  expect(localStorage.getItem(STORAGE_KEY)).toBe('dark')

  fireEvent.click(screen.getByRole('radio', { name: 'Auto' }))
  expect(root.dataset.theme).toBeUndefined()
  expect(localStorage.getItem(STORAGE_KEY)).toBeNull()
})

test('a remembered theme is applied on load and shown as selected', () => {
  localStorage.setItem(STORAGE_KEY, 'light')

  applyStoredTheme()
  render(<ThemeSwitch />)

  expect(root.dataset.theme).toBe('light')
  expect(screen.getByRole('radio', { name: 'Light' })).toBeChecked()
})

test('an unknown stored value falls back to Auto', () => {
  localStorage.setItem(STORAGE_KEY, 'sepia')

  applyStoredTheme()

  expect(root.dataset.theme).toBeUndefined()
})
