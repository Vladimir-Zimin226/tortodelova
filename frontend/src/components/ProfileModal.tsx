import React, {useEffect, useState} from "react";
import {
    getMyBalance,
    depositMyBalance,
    getMyPredictions,
} from "../api/client";
import type {Prediction} from "../types/api";

interface ProfileModalProps {
    isOpen: boolean;
    onClose: () => void;
}

export const ProfileModal: React.FC<ProfileModalProps> = ({
                                                              isOpen,
                                                              onClose,
                                                          }) => {
    const [balance, setBalance] = useState<number | null>(null);
    const [loadingBalance, setLoadingBalance] = useState(false);
    const [depositLoading, setDepositLoading] = useState(false);

    const [historyOpen, setHistoryOpen] = useState(false);
    const [historyLoading, setHistoryLoading] = useState(false);
    const [history, setHistory] = useState<Prediction[]>([]);

    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        if (!isOpen) return;
        const load = async () => {
            setLoadingBalance(true);
            setError(null);
            try {
                const b = await getMyBalance();
                setBalance(b.balance_credits);
            } catch (e: any) {
                setError(e?.message || "Не удалось загрузить баланс");
            } finally {
                setLoadingBalance(false);
            }
        };
        load();
    }, [isOpen]);

    const handleDeposit = async () => {
        const amountStr = prompt("На сколько кредитов пополнить баланс?", "10");
        if (!amountStr) return;

        const amount = Number(amountStr);
        if (!Number.isFinite(amount) || amount <= 0) return;

        try {
            setDepositLoading(true);
            const b = await depositMyBalance(amount, "Пополнение через профиль");
            setBalance(b.balance_credits);
        } catch (e: any) {
            alert(e?.message || "Ошибка пополнения");
        } finally {
            setDepositLoading(false);
        }
    };

    const openHistory = async () => {
        setHistoryOpen(true);
        setHistoryLoading(true);
        setError(null);
        try {
            const preds = await getMyPredictions();
            setHistory(preds);
        } catch (e: any) {
            setError(e?.message || "Не удалось загрузить историю");
        } finally {
            setHistoryLoading(false);
        }
    };

    if (!isOpen) return null;

    return (
        <>
            {/* Окно профиля */}
            <div className="auth-modal-backdrop" onClick={onClose}>
                <div className="auth-modal" onClick={(e) => e.stopPropagation()}>
                    <button
                        className="auth-modal-close"
                        onClick={onClose}
                        aria-label="Закрыть"
                    >
                        ×
                    </button>
                    <h2 className="auth-modal-title">Профиль</h2>
                    <p className="auth-modal-subtitle">
                        Баланс и история списаний за генерации.
                    </p>

                    {error && <div className="auth-modal-error">{error}</div>}

                    <div className="balance-card" style={{marginTop: "0.4rem"}}>
                        <div className="balance-title">Баланс</div>
                        <div className="balance-value">
                            {loadingBalance
                                ? "Загрузка..."
                                : balance !== null
                                    ? `${balance} кредитов`
                                    : "—"}
                        </div>
                        <button
                            className="btn-secondary"
                            onClick={handleDeposit}
                            disabled={depositLoading}
                        >
                            {depositLoading ? "Пополняем..." : "Пополнить"}
                        </button>
                    </div>

                    <button
                        className="btn-primary auth-modal-submit"
                        type="button"
                        onClick={openHistory}
                        disabled={historyLoading}
                    >
                        {historyLoading ? "Загружаем историю..." : "История"}
                    </button>
                </div>
            </div>

            {/* Окно с историей */}
            {historyOpen && (
                <div
                    className="auth-modal-backdrop"
                    onClick={() => setHistoryOpen(false)}
                >
                    <div
                        className="auth-modal auth-modal--history"
                        onClick={(e) => e.stopPropagation()}
                    >
                        <button
                            className="auth-modal-close"
                            onClick={() => setHistoryOpen(false)}
                            aria-label="Закрыть"
                        >
                            ×
                        </button>
                        <h2 className="auth-modal-title">История списаний</h2>
                        <p className="auth-modal-subtitle">
                            Дата, время, промпт и списание кредитов.
                        </p>

                        {error && <div className="auth-modal-error">{error}</div>}

                        {historyLoading && <div>Загрузка...</div>}

                        {!historyLoading && history.length === 0 && (
                            <div className="chat-empty">Пока нет платных генераций.</div>
                        )}

                        {!historyLoading && history.length > 0 && (
                            <div className="admin-table-wrapper">
                                <table className="admin-table">
                                    <thead>
                                    <tr>
                                        <th>Дата и время</th>
                                        <th>Промпт</th>
                                        <th>Списано</th>
                                    </tr>
                                    </thead>
                                    <tbody>
                                    {history.map((p) => (
                                        <tr key={p.id}>
                                            <td>{new Date(p.created_at).toLocaleString()}</td>
                                            <td>{p.prompt_ru}</td>
                                            <td>-{p.credits_spent}</td>
                                        </tr>
                                    ))}
                                    </tbody>
                                </table>
                            </div>
                        )}
                    </div>
                </div>
            )}
        </>
    );
};
