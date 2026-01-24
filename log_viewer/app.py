"""Minimal Flask app for viewing logs."""

from flask import Flask, render_template

app = Flask(__name__)


@app.route("/")
def index():
    """Render the log viewer shell page."""
    return render_template("logs.html")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5551, debug=True)
