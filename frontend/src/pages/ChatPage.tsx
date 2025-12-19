import React, {useEffect, useState} from "react";
import {useAuth} from "../providers/AuthProvider";
import {
    demoEnqueuePrediction,
    enqueuePrediction,
    getMyPredictions,
    getDemoPrediction,
    downloadPredictionImage,
} from "../api/client";
import type {Prediction} from "../types/api";
import {AuthModal} from "../components/AuthModal";

interface ChatMessage {
    id: string;
    role: "user" | "assistant";
    content: string;
    prediction?: Prediction;
}

const DEMO_COUNTER_KEY = "demoGenerationsUsed2";
const DEMO_TASK_ID_KEY = "demoTaskId";
const DEMO_PROMPT_KEY = "demoPrompt";

export const ChatPage: React.FC = () => {
    const {isAuthenticated} = useAuth();
    const [messages, setMessages] = useState<ChatMessage[]>([]);
    const [input, setInput] = useState("");
    const [loading, setLoading] = useState(false);
    const [showAuthModal, setShowAuthModal] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const loadInitialData = async () => {
        // Авторизованный пользователь — обычная история из /predictions
        if (isAuthenticated) {
            try {
                const preds = await getMyPredictions();

                const msgs: ChatMessage[] = [];
                for (const p of preds) {
                    msgs.push({
                        id: `u-${p.id}`,
                        role: "user",
                        content: p.prompt_ru,
                    });
                    msgs.push({
                        id: `a-${p.id}`,
                        role: "assistant",
                        content: `Сгенерированный дизайн (списано ${p.credits_spent} кредитов)`,
                        prediction: p,
                    });
                }

                setMessages(msgs);
            } catch {
                // игнорируем — чат просто будет пустым
            }
            return;
        }

        // Не авторизован — пробуем восстановить демо по task_id
        const taskId = localStorage.getItem(DEMO_TASK_ID_KEY);
        const prompt = localStorage.getItem(DEMO_PROMPT_KEY);
        if (!taskId || !prompt) return;

        try {
            const demoPred = await getDemoPrediction(taskId);
            const msgs: ChatMessage[] = [
                {
                    id: `demo-u-${demoPred.id}`,
                    role: "user",
                    content: prompt,
                },
                {
                    id: `demo-a-${demoPred.id}`,
                    role: "assistant",
                    content: "Сгенерированный демо-дизайн",
                    prediction: demoPred,
                },
            ];
            setMessages(msgs);
        } catch {
            // демо либо ещё не готово, либо уже не доступно — просто игнорируем
        }
    };

    useEffect(() => {
        loadInitialData();
    }, [isAuthenticated]);

    const handleGenerate = async () => {
        if (!input.trim()) return;
        setError(null);

        const demoUsed = Number(localStorage.getItem(DEMO_COUNTER_KEY) || "0");

        // Не авторизован и демо уже использовано — просим войти
        if (!isAuthenticated && demoUsed >= 1) {
            setShowAuthModal(true);
            return;
        }

        const prompt = input.trim();

        const userMsg: ChatMessage = {
            id: `user-${Date.now()}`,
            role: "user",
            content: prompt,
        };

        setMessages((prev) => [...prev, userMsg]);
        setInput("");
        setLoading(true);

        try {
            if (!isAuthenticated && demoUsed === 0) {
                // первая демо-генерация
                const response = await demoEnqueuePrediction(prompt);
                localStorage.setItem(DEMO_COUNTER_KEY, "1");
                localStorage.setItem(DEMO_TASK_ID_KEY, response.task_id);
                localStorage.setItem(DEMO_PROMPT_KEY, prompt);
            } else {
                // платный запрос
                await enqueuePrediction(prompt);
            }

            const assistantMsg: ChatMessage = {
                id: `assistant-${Date.now()}`,
                role: "assistant",
                content:
                    "Задача поставлена в очередь. Обновите историю, чтобы увидеть результат.",
            };
            setMessages((prev) => [...prev, assistantMsg]);
        } catch (e: any) {
            setError(e?.message || "Ошибка генерации");
        } finally {
            setLoading(false);
        }
    };

    const handleDownload = async (predictionId: number) => {
        try {
            const blob = await downloadPredictionImage(predictionId);
            const url = URL.createObjectURL(blob);

            const a = document.createElement("a");
            a.href = url;
            a.download = `prediction-${predictionId}.png`;
            document.body.appendChild(a);
            a.click();
            a.remove();

            URL.revokeObjectURL(url);
        } catch (e: any) {
            setError(e?.message || "Ошибка скачивания");
        }
    };

    const imageContainerStyle: React.CSSProperties = {
        position: "relative",
        display: "inline-block",
    };

    const downloadIconButtonStyle: React.CSSProperties = {
        position: "absolute",
        top: 10,
        right: 10,
        width: 36,
        height: 36,
        borderRadius: 10,
        border: "1px solid rgba(255,255,255,0.25)",
        background: "rgba(0,0,0,0.25)",
        color: "rgba(255,255,255,0.9)",
        cursor: "pointer",
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
        boxShadow: "0 2px 10px rgba(0,0,0,0.10)",
        backdropFilter: "blur(6px)",
        WebkitBackdropFilter: "blur(6px)",
        opacity: 0.85,
    };


    return (
        <>
            <div className="chat-page">
                <section className="chat-main">
                    {!isAuthenticated && (
                        <div className="chat-banner">
                            Вы не авторизованы — доступна одна пробная генерация. Чтобы продолжить,
                            зарегистрируйтесь в сервисе.
                        </div>
                    )}

                    <div className="chat-window">
                        {messages.map((m) => (
                            <div
                                key={m.id}
                                className={`chat-message chat-message-${m.role}`}
                            >
                                <div className="chat-badge">
                                    {m.role === "user" ? "Вы" : "Tortodelova"}
                                </div>
                                <div className="chat-text">{m.content}</div>

                                {m.prediction && (
                                    <div className="chat-image-wrapper">
                                        <div style={imageContainerStyle}>
                                            <img
                                                src={`/api/predictions/${m.prediction.id}/image`}
                                                alt="Сгенерированный торт"
                                            />

                                            {isAuthenticated && (
                                                <button
                                                    type="button"
                                                    onClick={() => handleDownload(m.prediction!.id)}
                                                    style={downloadIconButtonStyle}
                                                    title="Скачать"
                                                    aria-label="Скачать изображение"
                                                >
                                                    {/* Иконка "Download" (SVG) */}
                                                    <svg
                                                        width="18"
                                                        height="18"
                                                        viewBox="0 0 24 24"
                                                        fill="none"
                                                        xmlns="http://www.w3.org/2000/svg"
                                                        aria-hidden="true"
                                                    >
                                                        <path
                                                            d="M12 3v10m0 0l4-4m-4 4l-4-4"
                                                            stroke="currentColor"
                                                            strokeWidth="2"
                                                            strokeLinecap="round"
                                                            strokeLinejoin="round"
                                                        />
                                                        <path
                                                            d="M4 17v2a2 2 0 002 2h12a2 2 0 002-2v-2"
                                                            stroke="currentColor"
                                                            strokeWidth="2"
                                                            strokeLinecap="round"
                                                        />
                                                    </svg>
                                                </button>
                                            )}
                                        </div>
                                    </div>
                                )}
                            </div>
                        ))}

                        {messages.length === 0 && (
                            <div className="chat-empty">
                                Опишите желаемый торт и нажмите «Сгенерировать дизайн».
                            </div>
                        )}
                    </div>

                    <div className="chat-input-panel">
            <textarea
                rows={3}
                placeholder="Например: Нежный двухъярусный торт в пастельных тонах с ягодами малины и надписью «С днём рождения!»"
                value={input}
                onChange={(e) => setInput(e.target.value)}
            />
                        {error && <div className="chat-error">{error}</div>}
                        <button
                            className="btn-primary"
                            onClick={handleGenerate}
                            disabled={loading}
                        >
                            {loading ? "Генерируем..." : "Сгенерировать дизайн"}
                        </button>
                    </div>
                </section>
            </div>

            <AuthModal
                isOpen={showAuthModal}
                onClose={() => setShowAuthModal(false)}
                defaultMode="register"
            />
        </>
    );
};