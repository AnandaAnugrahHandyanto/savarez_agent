package kanbanui

import (
	"os"
	"path/filepath"
	"testing"
)

func TestStoreLoad(t *testing.T) {
	// Use the real kanban database if it exists.
	dbPath := os.Getenv("HERMES_KANBAN_DB")
	if dbPath == "" {
		home, err := os.UserHomeDir()
		if err != nil {
			t.Skip("no home dir")
		}
		dbPath = filepath.Join(home, ".hermes", "kanban.db")
	}

	if _, err := os.Stat(dbPath); os.IsNotExist(err) {
		t.Skip("kanban.db not found at", dbPath)
	}

	store := NewStore(dbPath)
	defer store.Close()

	if store.Path() != dbPath {
		t.Errorf("Path() = %q, want %q", store.Path(), dbPath)
	}

	snapshot := store.Load()
	if snapshot.LoadError != nil {
		t.Fatalf("Load() error: %v", snapshot.LoadError)
	}

	if len(snapshot.Columns) == 0 {
		t.Fatal("Load() returned no columns")
	}

	// Verify canonical column order.
	expected := ValidStatuses()
	if len(snapshot.Columns) != len(expected) {
		t.Errorf("columns = %d, want %d", len(snapshot.Columns), len(expected))
	}
	for i, col := range snapshot.Columns {
		if i < len(expected) && col.Status != expected[i] {
			t.Errorf("column[%d].Status = %q, want %q", i, col.Status, expected[i])
		}
	}

	// Verify tasks are sorted within columns.
	for _, col := range snapshot.Columns {
		for j := 1; j < len(col.Tasks); j++ {
			prev := col.Tasks[j-1]
			curr := col.Tasks[j]
			if prev.Assignee > curr.Assignee ||
				(prev.Assignee == curr.Assignee && prev.Title > curr.Title) {
				t.Errorf("tasks not sorted in column %q: %q > %q", col.Status, prev.Title, curr.Title)
			}
		}
	}

	t.Logf("Loaded %d columns, %d total tasks from %s", len(snapshot.Columns), len(snapshot.AllTasks()), snapshot.Source)
}

func TestStoreLoadFallback(t *testing.T) {
	// Test with a non-existent database — should fall back to placeholders.
	store := NewStore("/nonexistent/path/kanban.db")
	snapshot := store.Load()

	if snapshot.LoadError == nil {
		t.Fatal("expected error for non-existent DB, got nil")
	}

	// Should still have placeholder columns.
	if len(snapshot.Columns) == 0 {
		t.Fatal("expected fallback columns, got none")
	}
}

func TestTaskStatusConstants(t *testing.T) {
	statuses := ValidStatuses()
	expected := []TaskStatus{
		StatusTriage, StatusTodo, StatusReady,
		StatusRunning, StatusBlocked, StatusDone,
	}

	if len(statuses) != len(expected) {
		t.Fatalf("ValidStatuses() = %d, want %d", len(statuses), len(expected))
	}

	for i, want := range expected {
		if statuses[i] != want {
			t.Errorf("status[%d] = %q, want %q", i, statuses[i], want)
		}
	}

	// Verify terminal states.
	if !StatusDone.IsTerminal() {
		t.Error("StatusDone.IsTerminal() = false, want true")
	}
	for _, s := range expected {
		if s != StatusDone && s.IsTerminal() {
			t.Errorf("%q.IsTerminal() = true, want false", s)
		}
	}
}

func TestBoardSnapshotAllTasks(t *testing.T) {
	snapshot := BoardSnapshot{
		Columns: []Column{
			{Status: StatusTodo, Tasks: []Task{
				{ID: "a", Title: "A", Status: StatusTodo},
				{ID: "b", Title: "B", Status: StatusTodo},
			}},
			{Status: StatusDone, Tasks: []Task{
				{ID: "c", Title: "C", Status: StatusDone},
			}},
		},
	}

	all := snapshot.AllTasks()
	if len(all) != 3 {
		t.Errorf("AllTasks() = %d, want 3", len(all))
	}
}

func TestBoardSnapshotAllTasksEmpty(t *testing.T) {
	snapshot := BoardSnapshot{Columns: []Column{}}
	all := snapshot.AllTasks()
	if all != nil {
		t.Errorf("AllTasks() on empty snapshot = %v, want nil", all)
	}
}
