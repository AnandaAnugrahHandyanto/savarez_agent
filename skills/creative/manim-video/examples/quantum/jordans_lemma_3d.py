from manim import *

BG = "#1C1C1C"
PRIMARY = "#58C4DD"    # Blue
SECONDARY = "#FF6B6B"  # Red
ACCENT = "#83C167"     # Green
TEXT_COLOR = "#EAEAEA"

class Scene1_JordanLemma(ThreeDScene):
    def construct(self):
        self.camera.background_color = BG
        
        # Setup 3D camera
        self.set_camera_orientation(phi=75 * DEGREES, theta=30 * DEGREES)
        
        # Title that stays in 2D space
        title = Text("Jordan's Lemma", font_size=48, color=TEXT_COLOR).to_corner(UL)
        self.add_fixed_in_frame_mobjects(title)
        
        # 1. THE MAZE (High dimensions)
        axes = ThreeDAxes()
        self.add(axes)
        
        dots = VGroup(*[
            Dot3D(point=[
                np.random.uniform(-3, 3),
                np.random.uniform(-3, 3),
                np.random.uniform(-3, 3)
            ], radius=0.05, color=WHITE)
            for _ in range(50)
        ])
        
        self.add_subcaption("Imagine you are lost in a giant, multi-dimensional maze.", duration=5)
        self.play(Write(title))
        self.play(FadeIn(dots), run_time=2)
        
        # Rotate camera to show "millions of dimensions"
        self.move_camera(phi=60 * DEGREES, theta=120 * DEGREES, run_time=3)
        
        # 2. THE TWO MIRRORS (Reflections)
        self.add_subcaption("Grover's algorithm uses two magic mirrors—reflections.", duration=4)
        
        mirror1 = Surface(
            lambda u, v: np.array([u, v, 0]),
            u_range=[-3, 3], v_range=[-3, 3],
            resolution=(10, 10),
            fill_color=PRIMARY, fill_opacity=0.3, stroke_width=0
        )
        
        mirror2 = Surface(
            lambda u, v: np.array([u, u * 0.5, v]),
            u_range=[-3, 3], v_range=[-3, 3],
            resolution=(10, 10),
            fill_color=SECONDARY, fill_opacity=0.3, stroke_width=0
        )
        
        self.play(FadeOut(dots))
        self.play(Create(mirror1), Create(mirror2))
        self.wait(1)
        
        # 3. THE 2D PLANE (The Secret)
        self.add_subcaption("Jordan's Lemma proves bouncing between them traps you on a flat 2D plane.", duration=6)
        
        # We fade out the mirrors and show just the 2D plane they create
        self.move_camera(phi=0 * DEGREES, theta=-90 * DEGREES, run_time=2)
        self.play(FadeOut(mirror1), FadeOut(mirror2), FadeOut(axes))
        
        # 2D View now
        plane = NumberPlane(background_line_style={"stroke_opacity": 0.2})
        self.play(Create(plane))
        
        circle = Circle(radius=2, color=ACCENT)
        dot = Dot(point=[2, 0, 0], color=TEXT_COLOR, radius=0.1)
        
        self.play(Create(circle))
        self.play(FadeIn(dot))
        
        self.add_subcaption("Instead of wandering, you just walk in a straight circle to the answer!", duration=5)
        
        # Trace the circle (representing the rotation from the two reflections)
        self.play(MoveAlongPath(dot, circle), run_time=3, rate_func=linear)
        
        target_dot = Dot(point=[0, 2, 0], color=SECONDARY, radius=0.15)
        target_label = Text("Answer", font_size=24, color=SECONDARY).next_to(target_dot, UR, buff=0.1)
        
        self.play(FadeIn(target_dot), FadeIn(target_label))
        self.play(MoveAlongPath(dot, Arc(radius=2, start_angle=0, angle=PI/2)), run_time=1.5)
        self.play(Flash(target_dot, color=SECONDARY, line_length=0.5))
        
        self.wait(2)
        self.play(FadeOut(Group(*self.mobjects)))
