from manim import *

BG = "#1C1C1C"
PRIMARY = "#58C4DD"    # Blue (Z)
SECONDARY = "#FFFF00"  # Yellow (X)
ACCENT = "#83C167"     # Green (Intersection)
TEXT_COLOR = "#EAEAEA"

class Scene1_TheLattice(Scene):
    def construct(self):
        self.camera.background_color = BG
        
        # Title
        title = Text("The Bacon-Shor Code", font_size=48, color=TEXT_COLOR)
        self.add_subcaption("The Bacon-Shor code organizes qubits into a 2D grid.", duration=3)
        
        self.play(Write(title))
        self.wait(1)
        self.play(title.animate.to_edge(UP))
        
        # Create a 4x4 grid of dots representing qubits
        qubits = VGroup(*[Dot(radius=0.15, color=TEXT_COLOR) for _ in range(16)])
        qubits.arrange_in_grid(rows=4, cols=4, buff=1.0)
        
        self.play(LaggedStart(*[FadeIn(q, scale=0.5) for q in qubits], lag_ratio=0.05), run_time=1.5)
        self.wait(1)
        
        self.play(FadeOut(title), FadeOut(qubits))


class Scene2_Intersection(Scene):
    def construct(self):
        self.camera.background_color = BG
        
        # Recreate the 4x4 grid
        qubits = VGroup(*[Dot(radius=0.15, color=TEXT_COLOR) for _ in range(16)])
        qubits.arrange_in_grid(rows=4, cols=4, buff=1.0)
        self.add(qubits)
        
        # Highlight two adjacent columns (Z stabilizer)
        col_indices = [1, 2, 5, 6, 9, 10, 13, 14] # Columns 1 and 2 (0-indexed)
        z_stabilizer = VGroup(*[qubits[i] for i in col_indices])
        z_box = SurroundingRectangle(z_stabilizer, color=PRIMARY, fill_opacity=0.2, buff=0.3)
        
        self.add_subcaption("A Z-stabilizer protects against errors across two entire columns.", duration=3)
        self.play(Create(z_box), z_stabilizer.animate.set_color(PRIMARY))
        self.wait(1)
        
        # Highlight two adjacent rows (X stabilizer)
        row_indices = [4, 5, 6, 7, 8, 9, 10, 11] # Rows 1 and 2 (0-indexed)
        x_stabilizer = VGroup(*[qubits[i] for i in row_indices])
        x_box = SurroundingRectangle(x_stabilizer, color=SECONDARY, fill_opacity=0.2, buff=0.3)
        
        self.add_subcaption("An X-stabilizer protects across two entire rows.", duration=3)
        self.play(Create(x_box), x_stabilizer.animate.set_color(SECONDARY))
        self.wait(1)
        
        # The intersection
        intersection_indices = [5, 6, 9, 10]
        intersection_qubits = VGroup(*[qubits[i] for i in intersection_indices])
        intersection_box = SurroundingRectangle(intersection_qubits, color=ACCENT, fill_opacity=0.5, buff=0.4)
        
        self.add_subcaption("Notice where they overlap: exactly 4 qubits.", duration=3)
        self.play(
            Create(intersection_box),
            intersection_qubits.animate.set_color(ACCENT).scale(1.5),
            run_time=1.5
        )
        self.wait(2)
        
        # The explanation
        explanation = Text("Even overlap (4) = They Commute!", font_size=36, color=ACCENT)
        explanation.next_to(x_box, DOWN, buff=0.5)
        
        self.add_subcaption("In quantum mechanics, Pauli operators commute if they overlap on an even number of qubits. This is the secret of the code.", duration=4)
        self.play(Write(explanation))
        self.wait(3)
        
        self.play(FadeOut(Group(*self.mobjects)))
