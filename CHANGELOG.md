# Changelog

All notable changes to Nextup are recorded here.

## [0.7.1] — 2026-09-02

### Changed
- The clock choice is now a toggle switch reading "12 hours" and "24 hours",
  sitting beside the time rather than up beside the heading, since the time is
  the only thing it changes. It applies as soon as it is pressed, and still
  works without scripting.
- Hours and minutes are dropdowns rather than number boxes, so the 24 hour
  clock reads 08 and 09 rather than 8 and 9. A number box strips a leading
  zero, so it could never show them properly.

## [0.7.0] — 2026-09-02

### Added
- The morning email can go out at **any time of day, to the minute**, rather
  than on the hour. Twelve minutes past seven is a perfectly good answer.
- A small switch beside the heading turns the time controls from the 24 hour
  clock to **am and pm**, for anyone who would rather read it that way. The 24
  hour clock stays the default, and the choice only changes what is shown; the
  time is stored the same way either way.
- The email has been rebuilt: the Nextup name at the top, the date it covers,
  television and films in separate sections with the channel or the streaming
  service beside each, and a Lightmorphic credit at the foot linking to
  lightmorphic.com. Built from tables and inline styles, which is what mail
  clients understand, and it loads nothing from anywhere else.

### Changed
- The scheduler now checks every two minutes rather than every ten, so a time
  like 07:12 is not a quarter of an hour late.
- An older install that stored only an hour is read and converted on the way
  past, so nothing needs re-entering.

## [0.6.0] — 2026-09-02

### Added
- A setting for **when something counts as watchable**. A programme going out at
  eleven at night is not really available until the next day, so Nextup now
  waits a number of days you choose before putting it in Next up, moving a film
  into Ready to watch, or mentioning it in the email. The default is one day.
  Nought restores the old behaviour of counting it the day it airs.
- A **morning email**. Mail server details go in the Settings page, with the
  password stored encrypted alongside the TMDB key. Once a day it sends a short
  list of what has become watchable, in plain text and simple HTML. If nothing
  has, nothing is sent.
- Buttons to send a test message and to send today's email straight away,
  so the settings can be proved without waiting until morning.
- `TZ` in the compose file, since the send hour and the meaning of "today" both
  depend on the container's clock.

## [0.5.2] — 2026-09-02

### Fixed
- On a phone, the poster stayed beside the text on a show or film page, leaving
  the synopsis in a column about 190 pixels wide. Below 520 pixels the poster
  now sits above the text and the writing gets the full width.

## [0.5.1] — 2026-09-02

### Fixed
- The cast strip on a show or film page pushed the whole page off to the right
  instead of scrolling inside its own panel. The column it sits in was sizing
  itself to the full width of every cast photograph laid end to end.

## [0.5.0] — 2026-09-02

### Added
- Films now appear on the calendar, on the day they reach home viewing, in blue
  against the yellow used for episodes. Every entry is also labelled, so the two
  are told apart by more than colour, and a small key sits above the month.
- Films you have already seen are faded on the calendar the same way watched
  episodes are, rather than disappearing.

### Changed
- Films on the maybe list stay off the calendar, matching how maybe shows behave.

## [0.4.0] — 2026-09-02

### Added
- Show and film pages now carry proper detail: the cast with photographs, the
  genres, the certificate, the tagline, the creators of a series or the director
  and writers of a film, and links out to a trailer, IMDb and a where-to-watch
  page.
- Shows list which UK services carry them, the way films already did.
- Cast photographs go through the same local cache as posters, so the pages
  still call out to nobody.

### Changed
- The image proxy accepts filenames with dashes and underscores, which cast
  photographs use and posters do not.
- The extra detail is fetched when the page is opened rather than stored, so it
  is never stale, and both pages render fine when TMDB cannot be reached.

## [0.3.0] — 2026-09-02

### Added
- **Discover**, two pages for deciding what to take on. Films lists what reaches
  streaming or television in the next 7, 14, 30 or 60 days, with cinema releases
  left out. TV lists series starting soon, or everything on air now.
- A tick, a question mark and a cross on every Discover card. Tick adds it,
  question mark puts it on the Maybe list, cross hides it from Discover for
  good. Hidden items still turn up in a search, and one button brings them all
  back.
- **Episode pages.** Click any episode title and you get its still, synopsis,
  air date, runtime, rating, guest cast and director, with links to the episode
  either side. Episode titles across the dashboard, calendar, show pages and
  Coming soon all lead there.
- Films can go on the Maybe list too, so the tick, question mark and cross mean
  the same thing whichever page you are on. The Maybe page now has a Shows
  section and a Films section.

## [0.2.0] — 2026-09-02

### Added
- A **Maybe** list for shows you are curious about but are not following. They
  stay out of Next up, the calendar and Coming soon until you press Start
  watching, at which point they join your shows as normal.
- Search results and show pages can add straight to Maybe as well as to your
  shows.
- Films now show **when they reach streaming**, not just when they were in
  cinemas. Nextup reads the digital, physical and TV release dates from TMDB and
  prefers a UK one, falling back to Ireland then the US.
- Films also show **which UK services carry them**, using the JustWatch data
  TMDB publishes. Subscription, free and ad-supported services are listed;
  rental and purchase are left out.
- The Films page is now three sections: ready to watch, coming to streaming, and
  seen. A "Check now" button re-asks TMDB about any film without a date.
- Coming soon lists films landing on streaming alongside the episodes airing.

### Changed
- The scheduled refresh also updates film availability, and skips shows on the
  Maybe list.

## [0.1.0] — 2026-09-02

First working version.

### Added
- Next up dashboard: shows with aired, unwatched episodes, oldest first, with
  watched counts, time watched and a films-to-watch tile.
- My shows: poster grid with per-show progress, favourites, archive, and filters
  for all / behind / archived.
- Show page with every season and episode; tick one episode, a whole season, or
  everything up to a given episode.
- Month calendar of episodes for tracked shows, with watched ones faded.
- Coming soon list over 14, 30, 60 or 180 days.
- Film watchlist with a to-watch and a seen section.
- TMDB search across shows and films, added in one click.
- Automatic refresh from TMDB every 12 hours, plus a manual refresh button.
  Ended shows are refreshed on a two-week cycle instead.
- TMDB API key entered in the Settings page and stored encrypted, never in a
  plaintext environment file.
- Poster and still proxy: artwork is cached locally and served from this app, so
  no page loads anything from a third-party host.
- Light and dark themes, following the system by default, plus a 20-colour
  accent picker.
- Single-user sign-in with a starter account of admin / nextup that the app
  nags you to change.
