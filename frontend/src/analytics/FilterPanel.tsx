// Copyright 2025 Bush Ranger AI Project. All rights reserved.
import React from 'react';
import DateRangePicker, {
  DateRangePickerProps,
} from '@cloudscape-design/components/date-range-picker';
import Multiselect, { MultiselectProps } from '@cloudscape-design/components/multiselect';
import Button from '@cloudscape-design/components/button';
import SpaceBetween from '@cloudscape-design/components/space-between';
import FormField from '@cloudscape-design/components/form-field';
import type { FilterState } from './analyticsTypes';

/** The five IUCN conservation status categories. */
const IUCN_STATUS_OPTIONS: MultiselectProps.Option[] = [
  { label: 'Critically Endangered', value: 'critically_endangered' },
  { label: 'Endangered', value: 'endangered' },
  { label: 'Vulnerable', value: 'vulnerable' },
  { label: 'Near Threatened', value: 'near_threatened' },
  { label: 'Least Concern', value: 'least_concern' },
];

/** Returns the default FilterState: all species, all statuses, last 12 months. */
export function getDefaultFilters(): FilterState {
  const today = new Date();
  const twelveMonthsAgo = new Date(today);
  twelveMonthsAgo.setFullYear(twelveMonthsAgo.getFullYear() - 1);
  return {
    startDate: twelveMonthsAgo.toISOString().split('T')[0],
    endDate: today.toISOString().split('T')[0],
    species: [],
    statuses: [],
  };
}

export interface FilterPanelProps {
  filters: FilterState;
  onFilterChange: (filters: FilterState) => void;
  speciesList: string[];
}

export function FilterPanel({
  filters,
  onFilterChange,
  speciesList,
}: FilterPanelProps): React.JSX.Element {
  const speciesOptions: MultiselectProps.Option[] = speciesList.map((s) => ({
    label: s,
    value: s,
  }));

  const dateRangeValue: DateRangePickerProps.Value | null =
    filters.startDate && filters.endDate
      ? { type: 'absolute', startDate: filters.startDate, endDate: filters.endDate }
      : null;

  const selectedSpecies: MultiselectProps.Option[] = filters.species.map((s) => ({
    label: s,
    value: s,
  }));

  const selectedStatuses: MultiselectProps.Option[] = filters.statuses.map((s) => {
    const match = IUCN_STATUS_OPTIONS.find((opt) => opt.value === s);
    return match ?? { label: s, value: s };
  });

  const handleDateRangeChange = (detail: DateRangePickerProps.ChangeDetail) => {
    if (detail.value?.type === 'absolute') {
      onFilterChange({
        ...filters,
        startDate: detail.value.startDate,
        endDate: detail.value.endDate,
      });
    }
  };

  const handleSpeciesChange = (detail: MultiselectProps.MultiselectChangeDetail) => {
    onFilterChange({
      ...filters,
      species: detail.selectedOptions.map((opt) => opt.value ?? ''),
    });
  };

  const handleStatusChange = (detail: MultiselectProps.MultiselectChangeDetail) => {
    onFilterChange({
      ...filters,
      statuses: detail.selectedOptions.map((opt) => opt.value ?? ''),
    });
  };

  const handleReset = () => {
    onFilterChange(getDefaultFilters());
  };

  const isValidRange: DateRangePickerProps['isValidRange'] = (range) => {
    if (range === null) {
      return { valid: false, errorMessage: 'Select a date range.' };
    }
    if (range.type === 'absolute') {
      const [startDateOnly] = range.startDate.split('T');
      const [endDateOnly] = range.endDate.split('T');
      if (!startDateOnly || !endDateOnly) {
        return { valid: false, errorMessage: 'Select a start and end date.' };
      }
      if (new Date(range.startDate) > new Date(range.endDate)) {
        return { valid: false, errorMessage: 'Start date must be before end date.' };
      }
    }
    return { valid: true };
  };

  return (
    <SpaceBetween direction="horizontal" size="m">
      <FormField label="Date range">
        <DateRangePicker
          value={dateRangeValue}
          onChange={({ detail }) => handleDateRangeChange(detail)}
          isValidRange={isValidRange}
          dateOnly
          relativeOptions={[]}
          rangeSelectorMode="absolute-only"
          placeholder="Select date range"
          i18nStrings={{
            relativeModeTitle: 'Relative range',
            absoluteModeTitle: 'Absolute range',
            applyButtonLabel: 'Apply',
            cancelButtonLabel: 'Cancel',
            clearButtonLabel: 'Clear',
            startDateLabel: 'Start date',
            startTimeLabel: 'Start time',
            endDateLabel: 'End date',
            endTimeLabel: 'End time',
          }}
        />
      </FormField>
      <FormField label="Species">
        <Multiselect
          selectedOptions={selectedSpecies}
          onChange={({ detail }) => handleSpeciesChange(detail)}
          options={speciesOptions}
          placeholder="All species"
          filteringType="auto"
        />
      </FormField>
      <FormField label="Conservation status">
        <Multiselect
          selectedOptions={selectedStatuses}
          onChange={({ detail }) => handleStatusChange(detail)}
          options={IUCN_STATUS_OPTIONS}
          placeholder="All statuses"
        />
      </FormField>
      <FormField label="&nbsp;">
        <Button onClick={handleReset}>Reset filters</Button>
      </FormField>
    </SpaceBetween>
  );
}
