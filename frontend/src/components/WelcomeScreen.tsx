import { InputForm } from "./InputForm";

interface WelcomeScreenProps {
  handleSubmit: (
    submittedInputValue: string,
    effort: string,
    model: string
  ) => void;
  onCancel: () => void;
  isLoading: boolean;
}

export const WelcomeScreen: React.FC<WelcomeScreenProps> = ({
  handleSubmit,
  onCancel,
  isLoading,
}) => (
  <div className="flex flex-col items-center justify-center text-center px-6 flex-1 w-full max-w-4xl mx-auto gap-6">
    <div className="space-y-4">
      <h1 className="text-5xl md:text-7xl font-bold bg-gradient-to-r from-neutral-100 via-neutral-200 to-neutral-300 bg-clip-text text-transparent mb-4">
        Welcome.
      </h1>
      <p className="text-xl md:text-2xl text-neutral-400 leading-relaxed max-w-2xl mx-auto">
        How can I help you today?
      </p>
    </div>
    <div className="w-full mt-6 max-w-3xl">
      <InputForm
        onSubmit={handleSubmit}
        isLoading={isLoading}
        onCancel={onCancel}
        hasHistory={false}
      />
    </div>
    <p className="text-sm text-neutral-500 mt-4 flex items-center gap-2">
      <svg className="w-4 h-4 text-blue-400" fill="currentColor" viewBox="0 0 20 20">
        <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
      </svg>
      Powered by Azure OpenAI o3 models and LangChain LangGraph.
    </p>
  </div>
);
