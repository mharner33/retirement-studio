import { createContext } from "react";
import type { Errors } from "../pages/profileForm";

export const ErrorsContext = createContext<Errors>({});
