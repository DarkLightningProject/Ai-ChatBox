// src/Components/ImagePicker.jsx
import React, { useRef } from "react";

export default function ImagePicker({ images, setImages, disabled }) {
  const inputRef = useRef(null);

  const onPick = () => !disabled && inputRef.current?.click();

  const onChange = (e) => {
    const files = Array.from(e.target.files || []);
    if (!files.length) return;
    const next = [...images, ...files].slice(0, 4); // cap at 4
    setImages(next);
    e.target.value = ""; // reset
  };

  const removeAt = (idx) => {
    const copy = [...images];
    copy.splice(idx, 1);
    setImages(copy);
  };

  return (
    <div className="image-picker">
      <button
        type="button"
        className="btn add-btn"
        onClick={onPick}
        disabled={disabled || images.length >= 4}
        title={images.length >= 4 ? "Max 4 images" : "Add images"}
        aria-label="Add images"
      >
        <span className="plus-icon">＋</span>
      </button>

      <input
        ref={inputRef}
        type="file"
        accept=".png,.jpg,.jpeg,.webp"
        multiple
        style={{ display: "none" }}
        onChange={onChange}
      />

      {images.length > 0 && (
        <div className="thumbs">
          {images.map((f, i) => {
            const url = URL.createObjectURL(f);
            return (
              <div className="thumb" key={i} title={f.name}>
                <img src={url} alt={`preview-${i}`} onLoad={() => URL.revokeObjectURL(url)} />
                <button className="remove" onClick={() => removeAt(i)} aria-label="Remove image">×</button>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
