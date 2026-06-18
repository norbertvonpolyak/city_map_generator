import { useEffect, useId, useMemo, useRef, useState } from 'react'
import type { KeyboardEvent } from 'react'
import { huUiText } from '../../content/hu'
import type { SelectedLocation } from '../../services/locationSearch'
import { searchLocations } from '../../services/locationSearch'

interface LocationAutocompleteProps {
  value: string
  onSelect: (location: SelectedLocation) => void
}

export const LocationAutocomplete = ({ value, onSelect }: LocationAutocompleteProps) => {
  const [query, setQuery] = useState(value)
  const [items, setItems] = useState<SelectedLocation[]>([])
  const [isOpen, setIsOpen] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const [highlightedIndex, setHighlightedIndex] = useState(0)
  const [hasSearched, setHasSearched] = useState(false)
  const wrapperRef = useRef<HTMLDivElement | null>(null)
  const suppressNextSearchRef = useRef(false)
  const listId = useId()

  useEffect(() => {
    setQuery(value)
  }, [value])

  useEffect(() => {
    const onDocumentMouseDown = (event: MouseEvent) => {
      const target = event.target as Node | null
      if (wrapperRef.current && target && !wrapperRef.current.contains(target)) {
        setIsOpen(false)
      }
    }

    document.addEventListener('mousedown', onDocumentMouseDown)
    return () => {
      document.removeEventListener('mousedown', onDocumentMouseDown)
    }
  }, [])

  useEffect(() => {
    if (suppressNextSearchRef.current) {
      suppressNextSearchRef.current = false
      return
    }

    const trimmedQuery = query.trim()

    if (trimmedQuery.length < 3) {
      setIsLoading(false)
      setItems([])
      setIsOpen(false)
      setHasSearched(false)
      setHighlightedIndex(0)
      return
    }

    const abortController = new AbortController()
    setIsLoading(true)
    setHasSearched(true)

    const timeout = window.setTimeout(async () => {
      try {
        const results = await searchLocations(trimmedQuery, abortController.signal)
        setItems(results)
        setIsOpen(true)
        setHighlightedIndex(0)
      } catch (error) {
        if (error instanceof Error && error.name === 'AbortError') {
          return
        }
        setItems([])
        setIsOpen(true)
      } finally {
        setIsLoading(false)
      }
    }, 300)

    return () => {
      abortController.abort()
      window.clearTimeout(timeout)
    }
  }, [query])

  const hasResults = items.length > 0
  const shouldShowEmpty = hasSearched && !isLoading && !hasResults && query.trim().length >= 3
  const activeDescendant = isOpen && hasResults ? `${listId}-option-${highlightedIndex}` : undefined

  const selectBestMatch = (results: SelectedLocation[], rawQuery: string): SelectedLocation | null => {
    if (results.length === 0) {
      return null
    }

    const normalizedQuery = rawQuery.trim().toLocaleLowerCase()
    if (!normalizedQuery) {
      return results[0]
    }

    const startsWithMatch = results.find((item) => item.displayName.toLocaleLowerCase().startsWith(normalizedQuery))
    return startsWithMatch ?? results[0]
  }

  const selectLocation = (location: SelectedLocation) => {
    suppressNextSearchRef.current = true
    setQuery(location.displayName)
    setItems([])
    setIsOpen(false)
    setHasSearched(false)
    onSelect(location)
  }

  const searchAndSelectBest = async () => {
    const trimmedQuery = query.trim()
    if (trimmedQuery.length < 3) {
      return
    }

    setIsLoading(true)
    setHasSearched(true)

    try {
      const results = await searchLocations(trimmedQuery)
      setItems(results)
      setHighlightedIndex(0)
      setIsOpen(true)

      const bestMatch = selectBestMatch(results, trimmedQuery)
      if (bestMatch) {
        selectLocation(bestMatch)
      }
    } catch {
      setItems([])
      setIsOpen(true)
    } finally {
      setIsLoading(false)
    }
  }

  const selectAt = (index: number) => {
    if (index < 0 || index >= items.length) {
      return
    }
    selectLocation(items[index])
  }

  const onKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === 'Escape') {
      setIsOpen(false)
      return
    }

    if (!isOpen) {
      if (event.key === 'ArrowDown' && hasResults) {
        setIsOpen(true)
        event.preventDefault()
      }
      return
    }

    if (event.key === 'ArrowDown') {
      if (items.length === 0) {
        return
      }
      event.preventDefault()
      setHighlightedIndex((current) => (current + 1) % items.length)
      return
    }

    if (event.key === 'ArrowUp') {
      if (items.length === 0) {
        return
      }
      event.preventDefault()
      setHighlightedIndex((current) => (current - 1 + items.length) % items.length)
      return
    }

    if (event.key === 'Enter') {
      event.preventDefault()

      if (items.length > 0) {
        selectAt(highlightedIndex)
        return
      }

      void searchAndSelectBest()
    }
  }

  const listBoxContent = useMemo(() => {
    if (isLoading) {
      return <li className="umc-location-autocomplete-state">Keresés...</li>
    }

    if (shouldShowEmpty) {
      return <li className="umc-location-autocomplete-state">Nincs találat</li>
    }

    return items.map((item, index) => {
      const isHighlighted = index === highlightedIndex
      return (
        <li
          id={`${listId}-option-${index}`}
          key={`${item.displayName}-${item.lat}-${item.lon}`}
          role="option"
          aria-selected={isHighlighted}
          className={isHighlighted ? 'umc-location-autocomplete-item umc-location-autocomplete-item-active' : 'umc-location-autocomplete-item'}
          onMouseEnter={() => setHighlightedIndex(index)}
          onMouseDown={(event) => {
            event.preventDefault()
            selectAt(index)
          }}
        >
          {item.displayName}
        </li>
      )
    })
  }, [highlightedIndex, isLoading, items, listId, shouldShowEmpty])

  return (
    <div className="umc-location-autocomplete" ref={wrapperRef}>
      <input
        value={query}
        onChange={(event) => setQuery(event.target.value)}
        onFocus={() => {
          if (query.trim().length >= 3) {
            setIsOpen(true)
          }
        }}
        onKeyDown={onKeyDown}
        placeholder={huUiText.cityPlaceholder}
        className="umc-input umc-location-autocomplete-input"
        role="combobox"
        aria-expanded={isOpen}
        aria-controls={listId}
        aria-activedescendant={activeDescendant}
        aria-autocomplete="list"
      />
      {isOpen ? (
        <ul id={listId} role="listbox" className="umc-location-autocomplete-list">
          {listBoxContent}
        </ul>
      ) : null}
    </div>
  )
}
