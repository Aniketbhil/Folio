import io
import json
from pathlib import Path
import pymupdf
import pptx
from pptx.util import Inches, Pt


def _generate_figure_bytes() -> bytes:
    """Generate a sample 300x300 PNG diagram (Force vs Acceleration) for caption testing."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=(3.2, 3.2), dpi=100)
        ax.plot([0, 1, 2, 3], [0, 9.8, 19.6, 29.4], 'b-o', label="F = ma (m=9.8kg)")
        ax.set_xlabel("Acceleration (m/s²)", fontsize=9)
        ax.set_ylabel("Net Force (N)", fontsize=9)
        ax.set_title("Newton's 2nd Law Experiment", fontsize=10)
        ax.legend(fontsize=8)
        buf = io.BytesIO()
        fig.savefig(buf, format="png", bbox_inches="tight")
        plt.close(fig)
        return buf.getvalue()
    except Exception:
        pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 250, 250), 0)
        pix.set_rect(pix.irect, (180, 200, 240))
        return pix.tobytes("png")


def generate_all_samples(target_dir: Path) -> None:
    """Generate sample test files for PDF, PPTX, and transcript formats."""
    target_dir.mkdir(parents=True, exist_ok=True)
    sample_fig_bytes = _generate_figure_bytes()

    # 1. sample.pdf (5 pages with TOC, headings, paragraphs)
    pdf_doc = pymupdf.open()
    pages_data = [
        (
            "Introduction to Newton's Laws",
            "Sir Isaac Newton published his three laws of motion in the Mathematical Principles of "
            "Natural Philosophy in 1687. These principles form the cornerstone of classical mechanics, "
            "explaining the relationship between a body and the forces acting upon it.",
        ),
        (
            "First Law: The Principle of Inertia",
            "Newton's First Law states that every object continues in a state of rest or uniform motion "
            "in a straight line unless compelled to change its state by forces impressed upon it. "
            "Inertia is the inherent resistance of any physical object to any change in its velocity.",
        ),
        (
            "Second Law: Force and Acceleration",
            "The second law states that the acceleration of an object is dependent upon two variables: "
            "the net force acting upon the object and the mass of the object. Mathematically, it is "
            "expressed as F = ma, where force equals mass times acceleration.",
        ),
        (
            "Third Law: Action and Reaction",
            "The third law states that for every action, there is an equal and opposite reaction. "
            "When one body exerts a force on a second body, the second body simultaneously exerts a force "
            "equal in magnitude and opposite in direction upon the first body.",
        ),
        (
            "Applications of Classical Mechanics",
            "Newton's laws govern numerous modern technologies including vehicle safety systems, "
            "aerospace rocketry, satellite orbits, and biomechanics in athletic sports. Despite relativistic "
            "refinements by Einstein, Newtonian mechanics remains exceptionally accurate for everyday speeds.",
        ),
    ]

    toc_entries = []
    for idx, (title, body) in enumerate(pages_data):
        page = pdf_doc.new_page(width=595, height=842)
        page_num = idx + 1
        toc_entries.append([1, title, page_num])

        # Insert heading and text
        p1 = pymupdf.Point(50, 72)
        page.insert_text(p1, title, fontsize=18, fontname="helv", color=(0.1, 0.2, 0.5))

        rect = pymupdf.Rect(50, 110, 545, 750)
        page.insert_textbox(rect, body, fontsize=12, fontname="times-roman", color=(0, 0, 0))

    if len(pdf_doc) > 2:
        pdf_doc[2].insert_image(pymupdf.Rect(50, 280, 350, 580), stream=sample_fig_bytes)

    pdf_doc.set_toc(toc_entries)
    pdf_path = target_dir / "sample.pdf"
    pdf_doc.save(str(pdf_path))
    pdf_doc.close()
    print(f"Created: {pdf_path}")

    # 2. empty.pdf (2 blank pages, no text)
    empty_doc = pymupdf.open()
    empty_doc.new_page()
    empty_doc.new_page()
    empty_pdf_path = target_dir / "empty.pdf"
    empty_doc.save(str(empty_pdf_path))
    empty_doc.close()
    print(f"Created: {empty_pdf_path}")

    # 3. sample.pptx (6 slides: title, bullets, table, notes, empty)
    prs = pptx.Presentation()
    blank_layout = prs.slide_layouts[6]
    title_layout = prs.slide_layouts[0]
    bullet_layout = prs.slide_layouts[1]

    # Slide 1: Title slide
    s1 = prs.slides.add_slide(title_layout)
    s1.shapes.title.text = "Newton's Laws of Motion"
    s1.placeholders[1].text = "Foundations of Classical Dynamics\nPhysics 101 Lecture Series"
    s1.notes_slide.notes_text_frame.text = "Welcome students to the dynamics and mechanics course module."

    # Slide 2: Bullet slide
    s2 = prs.slides.add_slide(bullet_layout)
    s2.shapes.title.text = "First Law: Law of Inertia"
    tf2 = s2.placeholders[1].text_frame
    tf2.text = "Key Concepts of Inertia:"
    p2_1 = tf2.add_paragraph()
    p2_1.text = "• An isolated body remains at rest or moves with constant velocity."
    p2_2 = tf2.add_paragraph()
    p2_2.text = "• Mass is the fundamental scalar measure of an object's inertia."

    # Slide 3: Bullet slide with notes
    s3 = prs.slides.add_slide(bullet_layout)
    s3.shapes.title.text = "Second Law: Force and Mass (F=ma)"
    tf3 = s3.placeholders[1].text_frame
    tf3.text = "Mathematical Formulation:"
    p3_1 = tf3.add_paragraph()
    p3_1.text = "• Net external force causes acceleration proportional to magnitude."
    p3_2 = tf3.add_paragraph()
    p3_2.text = "• Standard SI unit of force is the Newton (1 N = 1 kg·m/s²)."
    s3.notes_slide.notes_text_frame.text = "Emphasize that acceleration is zero whenever net force equals zero."
    # Add diagram picture to slide 3
    s3.shapes.add_picture(io.BytesIO(sample_fig_bytes), Inches(5.2), Inches(2.0), width=Inches(4.0))

    # Slide 4: Table slide
    s4 = prs.slides.add_slide(blank_layout)
    # Add manual title box
    tb = s4.shapes.add_textbox(Inches(0.8), Inches(0.5), Inches(8), Inches(1))
    tb.text_frame.text = "Laws of Motion Summary Table"
    tb.text_frame.paragraphs[0].font.size = Pt(24)
    tb.text_frame.paragraphs[0].font.bold = True

    # Add table (4 rows, 2 columns)
    table_shape = s4.shapes.add_table(4, 2, Inches(0.8), Inches(1.8), Inches(8.4), Inches(3.5))
    table = table_shape.table
    table.cell(0, 0).text = "Newtonian Law"
    table.cell(0, 1).text = "Governing Equation / Principle"
    table.cell(1, 0).text = "First Law"
    table.cell(1, 1).text = "Inertia: Net Force = 0 implies a = 0"
    table.cell(2, 0).text = "Second Law"
    table.cell(2, 1).text = "F = m · a"
    table.cell(3, 0).text = "Third Law"
    table.cell(3, 1).text = "Action-Reaction: F_12 = -F_21"

    # Slide 5: Action & Reaction
    s5 = prs.slides.add_slide(bullet_layout)
    s5.shapes.title.text = "Third Law: Action and Reaction"
    tf5 = s5.placeholders[1].text_frame
    tf5.text = "Physical Interactions:"
    p5_1 = tf5.add_paragraph()
    p5_1.text = "• Forces always occur in pairs acting on distinct bodies."
    p5_2 = tf5.add_paragraph()
    p5_2.text = "• Rocket engines push exhaust gases downward; gas accelerates rocket upward."

    # Slide 6: Completely empty slide (should be skipped during ingestion)
    prs.slides.add_slide(blank_layout)

    pptx_path = target_dir / "sample.pptx"
    prs.save(str(pptx_path))
    print(f"Created: {pptx_path}")

    # 4. sample.vtt (3-4 minutes, with YouTube-style rolling duplicate lines)
    vtt_content = """WEBVTT

00:00:00.000 --> 00:00:15.000
Welcome to this lecture on Newton's laws of motion.
Today we will understand the fundamental rules governing mechanics.

00:00:15.000 --> 00:00:30.000
Today we will understand the fundamental rules governing mechanics.
First let us consider a stationary object on a frictionless surface.

00:00:30.000 --> 00:00:50.000
An object at rest stays at rest because of inertia.
Inertia resists any changes in velocity or direction.

00:00:50.000 --> 00:01:20.000
Now what happens when we apply an unbalanced force?
Newton's second law states that force is directly proportional to acceleration.

00:01:20.000 --> 00:01:50.000
If you push twice as hard the object accelerates twice as fast.
The formula F equals m a is the mathematical heart of classical mechanics.

00:01:50.000 --> 00:02:20.000
Finally we look at Newton's third law.
Every single action force creates an equal and opposite reaction force.

00:02:20.000 --> 00:03:00.000
When a swimmer pushes back against water the water pushes the swimmer forward.
That concludes our quick video overview of the three laws of motion.
"""
    vtt_path = target_dir / "sample.vtt"
    vtt_path.write_text(vtt_content.strip(), encoding="utf-8")
    print(f"Created: {vtt_path}")

    # 5. sample.srt (~3 minutes)
    srt_content = """1
00:00:00,000 --> 00:00:20,000
Welcome to the physics crash course on Newton's laws.

2
00:00:20,000 --> 00:00:45,000
Newton's first law defines the concept of inertia.

3
00:00:45,000 --> 00:01:15,000
Without external net force, an object's velocity remains constant.

4
00:01:15,000 --> 00:01:45,000
The second law introduces the quantitative formula F equals m a.

5
00:01:45,000 --> 00:02:15,000
The third law states forces always occur in matched action-reaction pairs.

6
00:02:15,000 --> 00:03:00,000
These three laws allow us to calculate planetary orbits and engineer bridges.
"""
    srt_path = target_dir / "sample.srt"
    srt_path.write_text(srt_content.strip(), encoding="utf-8")
    print(f"Created: {srt_path}")

    # 6. sample_youtube.json (YouTube transcript shape {"text", "start", "duration"})
    youtube_data = [
        {"text": "Hello everyone and welcome back to physics tutorial.", "start": 0.0, "duration": 18.0},
        {"text": "Today we are discussing Newton's first law of motion.", "start": 18.0, "duration": 22.0},
        {"text": "Inertia causes moving bodies to stay moving at constant velocity.", "start": 40.0, "duration": 25.0},
        {"text": "Next we move on to the second law relating force to acceleration.", "start": 65.0, "duration": 30.0},
        {"text": "Force is mass times acceleration which gives us the unit Newton.", "start": 95.0, "duration": 35.0},
        {"text": "And the third law states for every action there is an equal reaction.", "start": 130.0, "duration": 30.0},
        {"text": "Thank you for watching and remember to complete your practice problems.", "start": 160.0, "duration": 25.0},
    ]
    yt_path = target_dir / "sample_youtube.json"
    yt_path.write_text(json.dumps(youtube_data, indent=2), encoding="utf-8")
    print(f"Created: {yt_path}")

    # 7. sample_plain.txt (no timestamps, plain paragraphs)
    plain_content = """Newton's First Law describes the natural tendency of objects to resist changes in their state of motion. In the absence of an unbalanced external force, an object moving at five meters per second continues moving indefinitely.

Newton's Second Law provides the quantitative bridge between kinematics and dynamics. It states that acceleration is directly proportional to net force and inversely proportional to inertia or mass.

Newton's Third Law reveals the reciprocal nature of forces. A force cannot exist in isolation; every interaction requires two equal and opposite forces acting simultaneously upon two separate bodies."""
    plain_path = target_dir / "sample_plain.txt"
    plain_path.write_text(plain_content.strip(), encoding="utf-8")
    print(f"Created: {plain_path}")

    # 8. sample_timestamped.txt (lines like "[00:00] text")
    timestamped_content = """[00:00] In this recorded lecture segment we introduce the foundations of dynamics.
[00:35] Newton's first law explains the law of inertia for objects at rest or in uniform motion.
[01:10] Newton's second law links net force with acceleration through the equation F equals m a.
[01:50] Newton's third law shows that every action has an equal and opposite reaction force.
[02:30] These principles apply universally across classical mechanics and engineering problems."""
    ts_path = target_dir / "sample_timestamped.txt"
    ts_path.write_text(timestamped_content.strip(), encoding="utf-8")
    print(f"Created: {ts_path}")

    # 9. fake.docx (test unsupported file type)
    fake_path = target_dir / "fake.docx"
    fake_path.write_text("Dummy Word document content for testing 415 unsupported file type.", encoding="utf-8")
    print(f"Created: {fake_path}")


if __name__ == "__main__":
    samples_dir = Path(__file__).resolve().parent.parent / "samples"
    generate_all_samples(samples_dir)
