import { useState } from "react";
import { Button } from "@/components/ui/button";
import { SquarePen, Send, StopCircle } from "lucide-react";
import { Textarea } from "@/components/ui/textarea";

interface InputFormProps {
  onSubmit: (inputValue: string) => void;
  onCancel: () => void;
  isLoading: boolean;
  hasHistory: boolean;
}

export const InputForm: React.FC<InputFormProps> = ({
  onSubmit,
  onCancel,
  isLoading,
  hasHistory,
}) => {
  const [internalInputValue, setInternalInputValue] = useState("");

  const handleInternalSubmit = (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!internalInputValue.trim()) return;
    onSubmit(internalInputValue);
    setInternalInputValue("");
  };

  const handleInternalKeyDown = (
    e: React.KeyboardEvent<HTMLTextAreaElement>
  ) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleInternalSubmit();
    }
  };

  const isSubmitDisabled = !internalInputValue.trim() || isLoading;

  return (
    <form
      onSubmit={handleInternalSubmit}
      className="flex flex-col gap-3 p-4"
    >
      <div
        className={`flex flex-row items-center justify-between text-white rounded-2xl ${
          hasHistory ? "rounded-br-lg" : ""
        } break-words min-h-7 bg-neutral-700/90 backdrop-blur-sm border border-neutral-600/50 px-4 pt-3 shadow-lg`}
      >
        <Textarea
          value={internalInputValue}
          onChange={(e) => setInternalInputValue(e.target.value)}
          onKeyDown={handleInternalKeyDown}
          placeholder="Who won the Euro 2024 and scored the most goals?"
          className="w-full text-neutral-100 placeholder-neutral-400 resize-none border-0 focus:outline-none focus:ring-0 outline-none focus-visible:ring-0 shadow-none bg-transparent md:text-base min-h-[56px] max-h-[200px]"
          rows={1}
        />
        <div className="-mt-3">
          {isLoading ? (
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className="text-red-500 hover:text-red-400 hover:bg-red-500/10 p-2 cursor-pointer rounded-full transition-all duration-200 shadow-sm"
              onClick={onCancel}
            >
              <StopCircle className="h-5 w-5" />
            </Button>
          ) : (
            <Button
              type="submit"
              variant="ghost"
              className={`${
                isSubmitDisabled
                  ? "text-neutral-500"
                  : "text-blue-500 hover:text-blue-400 hover:bg-blue-500/10"
              } p-2 cursor-pointer rounded-full transition-all duration-200 text-base shadow-sm flex items-center gap-1.5`}
              disabled={isSubmitDisabled}
            >
              <span className="text-sm font-medium">Search</span>
              <Send className="h-4 w-4" />
            </Button>
          )}
        </div>
      </div>

      {hasHistory && (
        <div className="flex items-center justify-end mt-2">
          <Button
            className="bg-neutral-700/90 backdrop-blur-sm border border-neutral-600/50 text-neutral-300 hover:bg-neutral-600/90 hover:text-neutral-100 cursor-pointer rounded-xl px-4 py-2 shadow-sm transition-all duration-200 flex items-center gap-2"
            variant="outline"
            onClick={() => window.location.reload()}
          >
            <SquarePen size={16} />
            <span className="text-sm font-medium">New Search</span>
          </Button>
        </div>
      )}
    </form>
  );
};
