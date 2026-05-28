package kanbanui

import (
	"fmt"
	"strings"
	"time"

	"github.com/charmbracelet/bubbles/key"
	tea "github.com/charmbracelet/bubbletea"
	"github.com/charmbracelet/lipgloss"
)

type refreshMsg BoardSnapshot

// Init implements tea.Model.
func (m *Model) Init() tea.Cmd {
	return m.refreshCmd()
}

// Update implements tea.Model.
func (m *Model) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
	switch msg := msg.(type) {
	case tea.WindowSizeMsg:
		m.width = msg.Width
		m.height = msg.Height
		return m, nil
	case refreshMsg:
		snapshot := BoardSnapshot(msg)
		if snapshot.LoadError != nil {
			m.status = snapshot.LoadError.Error()
		} else {
			m.columns = snapshot.Columns
			m.tasks = snapshot.AllTasks()
			m.status = fmt.Sprintf("loaded %d tasks from %s", len(m.tasks), snapshot.Source)
		}
		return m, nil
	case tea.KeyMsg:
		switch {
		case key.Matches(msg, m.keymap.Quit):
			return m, tea.Quit
		case key.Matches(msg, m.keymap.Refresh):
			return m, m.refreshCmd()
		case key.Matches(msg, m.keymap.Up):
			if m.cursor > 0 {
				m.cursor--
			}
			return m, nil
		case key.Matches(msg, m.keymap.Down):
			if m.cursor < len(m.tasks)-1 {
				m.cursor++
			}
			return m, nil
		}
	}
	return m, nil
}

// View implements tea.Model.
func (m *Model) View() string {
	return m.render()
}

func (m *Model) refreshCmd() tea.Cmd {
	return func() tea.Msg {
		return refreshMsg(m.store.Load())
	}
}

func formatRefreshInterval(d time.Duration) string {
	if d <= 0 {
		return "manual"
	}
	return d.String()
}

func statusStyle(styles Styles, status TaskStatus) lipgloss.Style {
	if style, ok := styles.Status[string(status)]; ok {
		return style
	}
	return styles.Muted
}

func truncate(text string, width int) string {
	if width <= 0 || len(text) <= width {
		return text
	}
	if width <= 1 {
		return text[:width]
	}
	return strings.TrimSpace(text[:width-1]) + "…"
}
