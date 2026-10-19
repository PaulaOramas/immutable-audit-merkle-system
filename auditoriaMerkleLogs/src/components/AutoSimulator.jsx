/**
 * AutoSimulator — Control de simulación automática de eventos.
 */
import { useState, useRef, useEffect } from "react";

export default function AutoSimulator({ onGenerate, disabled }) {
  const [running, setRunning] = useState(false);
  const [speed, setSpeed] = useState(2000);
  const [count, setCount] = useState(10);
  const [generated, setGenerated] = useState(0);
  const intervalRef = useRef(null);
  const countRef = useRef(0);

  useEffect(() => {
    countRef.current = 0;
    setGenerated(0);
  }, [count]);

  function start() {
    setRunning(true);
    countRef.current = 0;
    setGenerated(0);
    intervalRef.current = setInterval(() => {
      if (countRef.current >= count) {
        stop();
        return;
      }
      onGenerate();
      countRef.current += 1;
      setGenerated(countRef.current);
    }, speed);
  }

  function stop() {
    setRunning(false);
    clearInterval(intervalRef.current);
    intervalRef.current = null;
  }

  useEffect(() => () => clearInterval(intervalRef.current), []);

  const progress = count > 0 ? (generated / count) * 100 : 0;

  return (
    <div className="auto-simulator">
      <h3 className="section-title">
        <span className="section-icon">🤖</span>
        Simulación Automática
      </h3>
      <div className="auto-controls">
        <div className="control-group">
          <label>Cantidad de eventos</label>
          <input
            type="number"
            min={1}
            max={100}
            value={count}
            onChange={(e) => setCount(Math.max(1, +e.target.value))}
            disabled={running}
          />
        </div>
        <div className="control-group">
          <label>Intervalo (ms)</label>
          <input
            type="range"
            min={200}
            max={5000}
            step={100}
            value={speed}
            onChange={(e) => setSpeed(+e.target.value)}
            disabled={running}
          />
          <span className="range-value">{speed}ms</span>
        </div>
        <button
          className={`btn ${running ? "btn-danger" : "btn-auto"}`}
          onClick={running ? stop : start}
          disabled={disabled}
        >
          {running ? "⏹ Detener" : "▶ Iniciar Ráfaga"}
        </button>
      </div>
      {(running || generated > 0) && (
        <div className="auto-progress">
          <div className="progress-bar">
            <div className="progress-fill" style={{ width: `${progress}%` }} />
          </div>
          <span className="progress-text">
            {generated} / {count} eventos
          </span>
        </div>
      )}
    </div>
  );
}
