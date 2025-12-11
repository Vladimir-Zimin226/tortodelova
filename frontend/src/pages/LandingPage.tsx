import React from "react";
import { useNavigate } from "react-router-dom";

export const LandingPage: React.FC = () => {
  const navigate = useNavigate();

  const goToApp = () => navigate("/app");

  return (
    <div className="landing">
      {/* Hero: для кого сервис + главное обещание */}
      <section className="hero">
        <span className="hero-pill">
          Онлайн-сервис для домашних кондитеров
        </span>

        <h1>Быстрые идеи для дизайна торта по одному промпту</h1>

        <p>
          Сервис помогает домашним кондитерам за минуты придумать
          оформление торта под любой заказ. Просто опишите идею торта —
          сервис предложит готовый визуальный дизайн.
        </p>

        <div className="hero-actions">
          <button className="btn-primary" onClick={goToApp}>
            Попробовать бесплатно
          </button>
        </div>
      </section>

      {/* Проблемы домашних кондитеров */}
      <section
        className="problems"
        aria-label="Проблемы, с которыми сталкиваются домашние кондитеры"
      >
        <h2>С чем вы сталкиваетесь, когда придумываете дизайн торта</h2>

        <div className="problem-grid">
          <article className="problem-card">
            <h3>Идеи приходят слишком долго</h3>
            <p>
              Вместо выпечки вы часами листаете картинки и сомневаетесь в
              результате.
            </p>
          </article>

          <article className="problem-card">
            <h3>Нельзя просто «взять» картинку</h3>
            <p>
              В интернете — чужие авторские работы. Использовать их один в один
              неэтично, а клиенту всё равно нужно что-то показать.
            </p>
          </article>

          <article className="problem-card">
            <h3>Обычные нейросети не понимают кондитеров</h3>
            <p>
              Генераторы картинок делают красиво, но не похоже на реальный
              торт, который можно собрать на кухне.
            </p>
          </article>
        </div>
      </section>

      {/* Решение */}
      <section className="solution" aria-label="Решение — Tortodelova">
        <h2>tortodelova решает эти проблемы</h2>
        <p>
          По вашему запросу сервис подбирает реалистичный дизайн торта,
          который можно воплотить дома. Все варианты
          сохраняются в личном кабинете — вы всегда можете вернуться к
          удачным идеям для повторных заказов.
        </p>
      </section>

      {/* Как работает */}
      <section
        className="how-it-works"
        aria-label="Как работает сервис Tortodelova"
      >
        <h2>Как это работает</h2>

        <ol className="steps-list">
          <li className="step-item">
            <span className="step-number">1</span>
            <div className="step-content">
              <h3>Опишите торт простыми словами</h3>
              <p>
                «Бисквит с малиной, крем-чиз, пастельные тона, надпись для
                дня рождения девочки 7 лет, немного съедобного золота».
              </p>
            </div>
          </li>

          <li className="step-item">
            <span className="step-number">2</span>
            <div className="step-content">
              <h3>Сервис генерирует дизайн</h3>
              <p>
                tortodelova переводит запрос и запускает ML-модели. Вы
                получаете визуальный дизайн торта, который можно показать
                клиенту или доработать.
              </p>
            </div>
          </li>

          <li className="step-item">
            <span className="step-number">3</span>
            <div className="step-content">
              <h3>Выбираете вариант, он сохраняется в истории</h3>
              <p>
                Понравившиеся дизайны остаются в вашей истории. К ним легко
                вернуться для повторных заказов или как базу для новых идей.
              </p>
            </div>
          </li>
        </ol>
      </section>

      {/* Преимущества */}
      <section
        className="benefits"
        aria-label="Преимущества сервиса для домашних кондитеров"
      >
        <h2>Что вы получаете с tortodelova</h2>

        <div className="benefit-grid">
          <article className="benefit-card">
            <h3>Экономия времени до 50%</h3>
            <p>
              Меньше часовых поисков референсов — больше времени на выпечку и
              сборку. Идеи для дизайна появляются за несколько минут.
            </p>
          </article>

          <article className="benefit-card">
            <h3>Доступная стоимость</h3>
            <p>
              Вы платите только за генерации, которые используете. Можно
              протестировать сервис на реальных заказах и масштабировать, когда
              почувствуете эффект.
            </p>
          </article>

          <article className="benefit-card">
            <h3>Удобный личный кабинет</h3>
            <p>
              Вся история дизайнов и запросов хранится в одном месте. Легко
              находить предыдущие торты по поводу, цветам или описанию клиента.
            </p>
          </article>
        </div>
      </section>

      {/* Нижний CTA */}
      <section className="bottom-cta" aria-label="Начать пользоваться сервисом">
        <div className="bottom-cta-inner">
          <h2>Попробуйте Tortodelova на своём следующем заказе</h2>
          <p>
            Сделайте первую бесплатную генерацию, покажите клиенту варианты
            дизайна и посмотрите, сколько времени вы сэкономите на согласовании.
          </p>
          <button className="btn-primary" onClick={goToApp}>
            Попробовать бесплатно
          </button>
        </div>
      </section>
    </div>
  );
};
