const { useState, useEffect } = React;

function App() {

  const [leftWidth, setLeftWidth] = useState(360);
  const [dragging, setDragging] = useState(false);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");

  useEffect(() => {
    function move(e) {
      if (!dragging) return;
      setLeftWidth(Math.max(300, Math.min(560, e.clientX)));
    }
    function up() { setDragging(false); }

    window.addEventListener("mousemove", move);
    window.addEventListener("mouseup", up);

    return () => {
      window.removeEventListener("mousemove", move);
      window.removeEventListener("mouseup", up);
    };
  }, [dragging]);

  async function sendMessage() {
    if (!input.trim()) return;

    const userMsg = { role: "user", text: input };
    setMessages(m => [...m, userMsg]);

    const res = await fetch("/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: input })
    });

    const data = await res.json();

    const aiMsg = { role: "assistant", text: data.response };
    setMessages(m => [...m, aiMsg]);

    setInput("");
  }

  return (
    React.createElement("div", {
      style: { display: "flex", height: "100vh", fontFamily: "Arial" }
    },

    // LEFT
    React.createElement("div", {
      style: { width:leftWidth, borderRight:"1px solid #ccc", padding:10 }
    },
      React.createElement("h3", null, "Hermes"),
      React.createElement("button", {
        onClick:()=>fetch("/restart",{method:"POST"})
      }, "Restart"),

      React.createElement("button", {
        onClick:async()=>{
          const r=await fetch("/status");
          const d=await r.json();
          alert(JSON.stringify(d,null,2));
        }
      }, "Status")
    ),

    // RESIZE BAR
    React.createElement("div", {
      style:{ width:5, cursor:"col-resize", background:"#eee"},
      onMouseDown:()=>setDragging(true)
    }),

    // RIGHT CHAT
    React.createElement("div", {
      style:{ flex:1, display:"flex", flexDirection:"column" }
    },

      React.createElement("div", {
        style:{ flex:1, padding:20, overflow:"auto" }
      },
        messages.map((m,i)=>
          React.createElement("div", {
            key:i,
            style:{ textAlign: m.role==="user"?"right":"left" }
          },
            React.createElement("div", {
              style:{
                display:"inline-block",
                padding:10,
                margin:5,
                borderRadius:10,
                background: m.role==="user"?"#000":"#eee",
                color: m.role==="user"?"#fff":"#000"
              }
            }, m.text)
          )
        )
      ),

      React.createElement("div", {
        style:{ display:"flex", borderTop:"1px solid #ccc" }
      },
        React.createElement("input", {
          value:input,
          onChange:e=>setInput(e.target.value),
          style:{ flex:1, padding:10 }
        }),
        React.createElement("button", {
          onClick:sendMessage
        }, "Send")
      )
    )
  ));
}

ReactDOM.createRoot(document.getElementById("root")).render(
  React.createElement(App)
);
