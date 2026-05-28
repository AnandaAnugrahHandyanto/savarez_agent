package kanbanui

import "time"

// Config holds runtime options for the kanban TUI.
type Config struct {
	DBPath          string
	RefreshInterval time.Duration
}

// Model is the Bubble Tea application state for the kanban board UI.
type Model struct {
	config Config
	store  Store
	keymap KeyMap
	styles Styles

	width   int
	height  int
	cursor  int
	columns []Column
	tasks   []Task
	status  string
}

// New creates a kanban UI model wired to the SQLite store.
func New(config Config) *Model {
	if config.RefreshInterval <= 0 {
		config.RefreshInterval = 2 * time.Second
	}

	store := NewStore(config.DBPath)
	return &Model{
		config: config,
		store:  store,
		keymap: DefaultKeyMap(),
		styles: DefaultStyles(),
	}
}
