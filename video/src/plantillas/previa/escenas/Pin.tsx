import React from "react";
import { useColores } from "../../../base/comun";

/** Icono de ubicación (campo) en el color de acento. */
export const Pin: React.FC<{ lado: number }> = ({ lado }) => {
  const c = useColores();
  return (
    <svg width={lado} height={lado} viewBox="0 0 24 24" style={{ flexShrink: 0 }}>
      <path
        d="M12 2C8.1 2 5 5.1 5 9c0 5.2 7 13 7 13s7-7.8 7-13c0-3.9-3.1-7-7-7zm0 9.5a2.5 2.5 0 1 1 0-5 2.5 2.5 0 0 1 0 5z"
        fill={c.acento}
      />
    </svg>
  );
};
