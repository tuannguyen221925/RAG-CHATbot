export const AVATARS = [
  { id: "default", name: "Mặc định", emoji: "", background: "", color: "" },
  {
    id: "robot",
    name: "Robot",
    emoji: "🤖",
    background: "#e2f1ff",
    color: "#345e82",
  },
  {
    id: "fox",
    name: "Cáo nhỏ",
    emoji: "🦊",
    background: "#fff0df",
    color: "#995823",
  },
  {
    id: "cat",
    name: "Mèo con",
    emoji: "🐱",
    background: "#fff4d7",
    color: "#9e7730",
  },
  {
    id: "panda",
    name: "Gấu trúc",
    emoji: "🐼",
    background: "#e5f3ec",
    color: "#356650",
  },
  {
    id: "flower",
    name: "Hoa anh đào",
    emoji: "🌸",
    background: "#ffe8f1",
    color: "#aa537e",
  },
  {
    id: "leaf",
    name: "Mầm xanh",
    emoji: "🌿",
    background: "#eaf4df",
    color: "#4d713b",
  },
  {
    id: "moon",
    name: "Trăng nhỏ",
    emoji: "🌙",
    background: "#283345",
    color: "#f0d59a",
  },
  {
    id: "planet",
    name: "Hành tinh",
    emoji: "🪐",
    background: "#ede6ff",
    color: "#6e51a1",
  },
  {
    id: "rocket",
    name: "Tên lửa",
    emoji: "🚀",
    background: "#e5ecfc",
    color: "#426298",
  },
];
export const getAvatarPreset = (id) =>
  AVATARS.find((item) => item.id === id) || AVATARS[0];
