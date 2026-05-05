.PHONY: validate-cloudshell-fog-structural validate-cloudshell-fog-upstream validate-cloudshell-fog-release validate-cloudshell-fog-go-live-standard validate-cloudshell-fog-go-live-federal validate-cloudshell-fog-platform-standard validate-cloudshell-fog-platform-federal

validate-cloudshell-fog-structural:
	bash tools/validate-cloudshell-fog-v2.sh structural

validate-cloudshell-fog-upstream:
	bash tools/validate-cloudshell-fog-v2.sh upstream

validate-cloudshell-fog-release:
	bash tools/validate-cloudshell-fog-v2.sh release

validate-cloudshell-fog-go-live-standard:
	bash tools/validate-cloudshell-fog-v2.sh go-live standard

validate-cloudshell-fog-go-live-federal:
	bash tools/validate-cloudshell-fog-v2.sh go-live federal

validate-cloudshell-fog-platform-standard:
	bash tools/validate-cloudshell-fog-v2.sh platform standard

validate-cloudshell-fog-platform-federal:
	bash tools/validate-cloudshell-fog-v2.sh platform federal
