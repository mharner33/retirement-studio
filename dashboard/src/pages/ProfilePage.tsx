import { Fragment, useEffect, useState } from "react";
import { ApiError, getJson, putJson } from "../api";
import { ErrorsContext } from "../components/errors";
import type { Household } from "../types";
import {
  AccountsSection,
  AssumptionsSection,
  IncomeSection,
  PersonSection,
  SpendingSection,
} from "./ProfileSections";
import {
  STEPS,
  blankHousehold,
  blankPerson,
  parseErrors,
  stepForPath,
  type Errors,
} from "./profileForm";

type Load = "loading" | "failed" | "ready";

export function ProfilePage() {
  const [load, setLoad] = useState<Load>("loading");
  const [exists, setExists] = useState(false);
  const [household, setHousehold] = useState<Household>(blankHousehold);
  const [step, setStep] = useState(0);
  const [errors, setErrors] = useState<Errors>({});
  const [message, setMessage] = useState("");

  useEffect(() => {
    getJson<Household>("/api/profile").then(
      (saved) => {
        setHousehold(saved);
        setExists(true);
        setLoad("ready");
      },
      (err: unknown) => {
        setLoad(err instanceof ApiError && err.status === 404 ? "ready" : "failed");
      },
    );
  }, []);

  function change(next: Household): void {
    setHousehold(next);
    setMessage("");
  }

  async function save(): Promise<void> {
    try {
      const saved = await putJson<Household>("/api/profile", household);
      setHousehold(saved);
      setExists(true);
      setErrors({});
      setMessage("Profile saved");
    } catch (err) {
      if (err instanceof ApiError && err.status === 422) {
        const found = parseErrors(err.detail);
        setErrors(found);
        const first = Object.keys(found)[0];
        if (first !== undefined) setStep(stepForPath(first));
        setMessage("Fix the highlighted fields");
      } else {
        setMessage("Could not save the profile");
      }
    }
  }

  if (load === "loading") return <p className="secondary">Loading</p>;
  if (load === "failed") {
    return (
      <p className="secondary" role="alert">
        Could not load the profile
      </p>
    );
  }

  const spouse = household.spouse;
  const you = (
    <PersonSection
      title="You"
      path="self"
      person={household.self}
      onChange={(p) => {
        change({ ...household, self: p });
      }}
    />
  );
  const spouseSection = spouse ? (
    <>
      <PersonSection
        title="Spouse"
        path="spouse"
        person={spouse}
        onChange={(p) => {
          change({ ...household, spouse: p });
        }}
      />
      <button
        type="button"
        className="secondary-button"
        onClick={() => {
          change({ ...household, spouse: null });
        }}
      >
        Remove spouse
      </button>
    </>
  ) : (
    <div className="card section">
      <p className="secondary">Add a spouse to plan together.</p>
      <button
        type="button"
        className="primary"
        onClick={() => {
          change({ ...household, spouse: blankPerson() });
        }}
      >
        Add spouse
      </button>
    </div>
  );
  const income = (
    <>
      <IncomeSection
        title="Your income"
        path="self"
        person={household.self}
        onChange={(p) => {
          change({ ...household, self: p });
        }}
      />
      {spouse && (
        <IncomeSection
          title="Spouse income"
          path="spouse"
          person={spouse}
          onChange={(p) => {
            change({ ...household, spouse: p });
          }}
        />
      )}
    </>
  );
  const accounts = (
    <AccountsSection
      accounts={household.accounts}
      onChange={(a) => {
        change({ ...household, accounts: a });
      }}
    />
  );
  const spending = (
    <SpendingSection
      spending={household.spending}
      onChange={(s) => {
        change({ ...household, spending: s });
      }}
    />
  );
  const assumptions = <AssumptionsSection household={household} onChange={change} />;

  const sections = [you, spouseSection, income, accounts, spending, assumptions];
  const last = step === STEPS.length - 1;
  const status = message && (
    <p className="secondary" role="status">
      {message}
    </p>
  );

  return (
    <ErrorsContext value={errors}>
      <h2>Profile</h2>
      {exists ? (
        <>
          {STEPS.map((name, i) => (
            <Fragment key={name}>{sections[i]}</Fragment>
          ))}
          <div className="actions">
            <button type="button" className="primary" onClick={() => void save()}>
              Save
            </button>
            {status}
          </div>
        </>
      ) : (
        <>
          <ol className="steps" aria-label="Steps">
            {STEPS.map((name, i) => (
              <li key={name} aria-current={i === step ? "step" : undefined}>
                {name}
              </li>
            ))}
          </ol>
          {sections[step]}
          <div className="actions">
            <button
              type="button"
              className="secondary-button"
              disabled={step === 0}
              onClick={() => {
                setStep(step - 1);
              }}
            >
              Back
            </button>
            {last ? (
              <button type="button" className="primary" onClick={() => void save()}>
                Save
              </button>
            ) : (
              <button
                type="button"
                className="primary"
                onClick={() => {
                  setStep(step + 1);
                }}
              >
                Next
              </button>
            )}
            {status}
          </div>
        </>
      )}
    </ErrorsContext>
  );
}
