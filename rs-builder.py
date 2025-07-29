import streamlit as st
from io import BytesIO
from xhtml2pdf import pisa

st.title("Textfield to HTML → PDF Generator")

# Input fields
name = st.text_input("Enter your Name")
address = st.text_area("Enter your Address")
message = st.text_area("Enter your Message")

# Build HTML
def build_html(name, address, message):
    return f"""
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; padding: 20px; }}
            h1 {{ color: #333; }}
            .section {{ margin-bottom: 15px; }}
        </style>
    </head>
    <body>
        <h1>Printable Document</h1>
        <div class="section"><strong>Name:</strong> {name}</div>
        <div class="section"><strong>Address:</strong><br>{address.replace('\n', '<br>')}</div>
        <div class="section"><strong>Message:</strong><br>{message.replace('\n', '<br>')}</div>
    </body>
    </html>
    """

# Convert HTML to PDF
def convert_html_to_pdf(source_html):
    output = BytesIO()
    pisa_status = pisa.CreatePDF(src=source_html, dest=output)
    if pisa_status.err:
        return None
    return output

# Preview HTML button
if st.button("💡 Preview HTML"):
    html_content = build_html(name, address, message)
    st.session_state["html_preview"] = html_content  # Save to session

# Show preview and generate/download if preview exists
if "html_preview" in st.session_state:
    st.subheader("HTML Preview")
    st.components.v1.html(st.session_state["html_preview"], height=400, scrolling=True)

    if st.button("📄 Generate & Download PDF"):
        pdf = convert_html_to_pdf(st.session_state["html_preview"])
        if pdf:
            st.success("✅ PDF generated successfully!")
            st.download_button(
                "⬇️ Download PDF",
                data=pdf,
                file_name="output.pdf",
                mime="application/pdf"
            )
        else:
            st.error("❌ Failed to generate PDF.")
