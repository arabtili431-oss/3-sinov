"""Kurslar, kategoriyalar, modullar va darslar."""
from django.contrib import messages
from django.db.models import Count, Prefetch, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from core.services import telegram_files
from courses.models import (
    Category,
    Course,
    Lesson,
    LessonAttachment,
    LessonQuiz,
    Module,
    QuizChoice,
    QuizQuestion,
)

from .forms import (
    CategoryForm,
    CourseForm,
    LessonAttachmentForm,
    LessonForm,
    LessonQuizSettingsForm,
    ModuleForm,
)
from .utils import notify_deleted, notify_saved, paginate, staff_required


# ------------------------------------------------------------ Kategoriyalar
@staff_required
def category_list(request):
    qs = Category.objects.annotate(courses_total=Count("courses")).order_by("order", "name")
    return render(request, "panel/courses/categories.html", {
        "page_title": _("Kurs kategoriyalari"),
        "page": paginate(request, qs, 30),
    })


@staff_required
def category_form(request, pk=None):
    obj = get_object_or_404(Category, pk=pk) if pk else None
    form = CategoryForm(request.POST or None, request.FILES or None, instance=obj)
    if request.method == "POST" and form.is_valid():
        created = obj is None
        notify_saved(request, form.save(), created=created)
        return redirect("panel:category_list")
    return render(request, "panel/courses/category_form.html", {
        "page_title": _("Kategoriya qo'shish") if not obj else _("Kategoriyani tahrirlash"),
        "form": form, "obj": obj,
        "back_url": reverse("panel:category_list"),
        "delete_url": reverse("panel:category_delete", args=[obj.pk]) if obj else None,
    })


@staff_required
@require_POST
def category_delete(request, pk):
    obj = get_object_or_404(Category, pk=pk)
    notify_deleted(request, obj)
    obj.delete()
    return redirect("panel:category_list")


# ------------------------------------------------------------------ Kurslar
@staff_required
def course_list(request):
    qs = Course.objects.select_related("category", "teacher").annotate(
        students=Count("enrollments", distinct=True),
        lessons_total=Count("modules__lessons", distinct=True),
    )

    search = (request.GET.get("q") or "").strip()
    category = request.GET.get("category") or ""
    access = request.GET.get("access") or ""
    status = request.GET.get("status") or ""

    if search:
        qs = qs.filter(Q(title__icontains=search) | Q(short_description__icontains=search))
    if category:
        qs = qs.filter(category_id=category)
    if access:
        qs = qs.filter(access=access)
    if status == "active":
        qs = qs.filter(is_active=True)
    elif status == "inactive":
        qs = qs.filter(is_active=False)

    return render(request, "panel/courses/list.html", {
        "page_title": _("Kurslar"),
        "page": paginate(request, qs.order_by("order", "-created_at")),
        "categories": Category.objects.all(),
        "access_choices": Course.ACCESS_CHOICES,
        "search": search, "category": category, "access": access, "status": status,
    })


@staff_required
def course_form(request, pk=None):
    obj = get_object_or_404(Course, pk=pk) if pk else None
    form = CourseForm(request.POST or None, request.FILES or None, instance=obj)
    if request.method == "POST" and form.is_valid():
        created = obj is None
        course = form.save()
        notify_saved(request, course, created=created)
        return redirect("panel:course_content", pk=course.pk)
    return render(request, "panel/courses/form.html", {
        "page_title": _("Kurs qo'shish") if not obj else _("Kursni tahrirlash"),
        "form": form, "obj": obj,
        "back_url": reverse("panel:course_list"),
        "delete_url": reverse("panel:course_delete", args=[obj.pk]) if obj else None,
    })


@staff_required
@require_POST
def course_delete(request, pk):
    obj = get_object_or_404(Course, pk=pk)
    # Telegramdagi videolarni ham tozalaymiz
    for lesson in Lesson.objects.filter(module__course=obj).exclude(telegram_message_id=None):
        telegram_files.delete_message(lesson.telegram_message_id)
    notify_deleted(request, obj)
    obj.delete()
    return redirect("panel:course_list")


@staff_required
@require_POST
def course_toggle(request, pk):
    obj = get_object_or_404(Course, pk=pk)
    obj.is_active = not obj.is_active
    obj.save(update_fields=["is_active"])
    messages.success(request, _("Kurs yoqildi.") if obj.is_active else _("Kurs o'chirildi."))
    return redirect(request.META.get("HTTP_REFERER") or "panel:course_list")


# ---------------------------------------------------- Kurs ichidagi darslar
@staff_required
def course_content(request, pk):
    """Kurs → modullar → darslar daraxti."""
    course = get_object_or_404(
        Course.objects.prefetch_related(
            Prefetch("modules", queryset=Module.objects.prefetch_related("lessons"))
        ),
        pk=pk,
    )
    return render(request, "panel/courses/content.html", {
        "page_title": course.title,
        "course": course,
        "module_form": ModuleForm(),
        "telegram_ready": telegram_files.is_configured(),
        "local_api": telegram_files.is_local_api(),
    })


@staff_required
def module_form(request, course_pk, pk=None):
    course = get_object_or_404(Course, pk=course_pk)
    obj = get_object_or_404(Module, pk=pk, course=course) if pk else None
    form = ModuleForm(request.POST or None, instance=obj)
    if request.method == "POST" and form.is_valid():
        module = form.save(commit=False)
        module.course = course
        if not obj and not module.order:
            module.order = course.modules.count() + 1
        module.save()
        notify_saved(request, module, created=obj is None)
        return redirect("panel:course_content", pk=course.pk)
    return render(request, "panel/courses/module_form.html", {
        "page_title": _("Modul qo'shish") if not obj else _("Modulni tahrirlash"),
        "form": form, "course": course, "obj": obj,
    })


@staff_required
@require_POST
def module_delete(request, course_pk, pk):
    module = get_object_or_404(Module, pk=pk, course_id=course_pk)
    for lesson in module.lessons.exclude(telegram_message_id=None):
        telegram_files.delete_message(lesson.telegram_message_id)
    notify_deleted(request, module)
    module.delete()
    return redirect("panel:course_content", pk=course_pk)


@staff_required
def lesson_form(request, course_pk, pk=None):
    course = get_object_or_404(Course, pk=course_pk)
    obj = get_object_or_404(Lesson, pk=pk, module__course=course) if pk else None
    form = LessonForm(request.POST or None, request.FILES or None, instance=obj, course=course)

    if request.method == "POST" and form.is_valid():
        lesson = form.save(commit=False)
        video = form.cleaned_data.get("video_file")

        # Videoni yopiq Telegram kanalga yuklaymiz
        if video:
            try:
                result = telegram_files.upload_video(
                    video, video.name,
                    caption=f"{course.title} / {lesson.title}",
                    duration=lesson.duration,
                )
                # Eski videoni kanaldan o'chiramiz
                if obj and obj.telegram_message_id:
                    telegram_files.delete_message(obj.telegram_message_id)
                lesson.telegram_file_id = result["file_id"]
                lesson.telegram_message_id = result["message_id"]
                lesson.video_size = result["size"]
                lesson.video_source = Lesson.VIDEO_TELEGRAM
                if result.get("duration") and not lesson.duration:
                    lesson.duration = result["duration"]
            except telegram_files.TelegramStorageError as exc:
                messages.error(request, str(exc))
                return render(request, "panel/courses/lesson_form.html", {
                    "page_title": _("Dars"), "form": form, "course": course, "obj": obj,
                    "telegram_ready": telegram_files.is_configured(),
                })

        if not obj and not lesson.order:
            lesson.order = lesson.module.lessons.count() + 1
        lesson.save()
        form.save_m2m()

        # Qo'shimcha fayllar
        for f in request.FILES.getlist("attachments"):
            LessonAttachment.objects.create(lesson=lesson, title=f.name, file=f, size=f.size)

        notify_saved(request, lesson, created=obj is None)
        return redirect("panel:course_content", pk=course.pk)

    return render(request, "panel/courses/lesson_form.html", {
        "page_title": _("Dars qo'shish") if not obj else _("Darsni tahrirlash"),
        "form": form, "course": course, "obj": obj,
        "telegram_ready": telegram_files.is_configured(),
        "local_api": telegram_files.is_local_api(),
    })


@staff_required
@require_POST
def lesson_delete(request, course_pk, pk):
    lesson = get_object_or_404(Lesson, pk=pk, module__course_id=course_pk)
    if lesson.telegram_message_id:
        telegram_files.delete_message(lesson.telegram_message_id)
    notify_deleted(request, lesson)
    lesson.delete()
    return redirect("panel:course_content", pk=course_pk)


@staff_required
@require_POST
def lesson_toggle(request, course_pk, pk):
    lesson = get_object_or_404(Lesson, pk=pk, module__course_id=course_pk)
    lesson.is_active = not lesson.is_active
    lesson.save(update_fields=["is_active"])
    messages.success(request, _("Dars yoqildi.") if lesson.is_active else _("Dars bloklandi."))
    return redirect("panel:course_content", pk=course_pk)


@staff_required
@require_POST
def attachment_delete(request, pk):
    att = get_object_or_404(LessonAttachment, pk=pk)
    course_pk = att.lesson.module.course_id
    att.delete()
    messages.success(request, _("Fayl o'chirildi."))
    return redirect("panel:course_content", pk=course_pk)


# --------------------------------------------------------------- Dars testi
@staff_required
def quiz_manage(request, course_pk, pk):
    """Dars testi: Coin sozlamalari + savol/javoblarni boshqarish."""
    lesson = get_object_or_404(Lesson, pk=pk, module__course_id=course_pk)
    quiz, _created = LessonQuiz.objects.get_or_create(lesson=lesson)

    if request.method == "POST" and request.POST.get("form") == "settings":
        form = LessonQuizSettingsForm(request.POST, instance=quiz)
        if form.is_valid():
            form.save()
            messages.success(request, _("Test sozlamalari saqlandi."))
            return redirect("panel:quiz_manage", course_pk=course_pk, pk=pk)
    else:
        form = LessonQuizSettingsForm(instance=quiz)

    if request.method == "POST" and request.POST.get("form") == "question":
        text = (request.POST.get("text") or "").strip()
        choices = [
            (request.POST.get(f"choice_{i}") or "").strip() for i in range(1, 5)
        ]
        correct_index = request.POST.get("correct")
        if not text or not all(choices) or correct_index not in {"1", "2", "3", "4"}:
            messages.error(request, _("Savol matni va barcha 4 ta javob variantini to'ldiring, to'g'ri javobni belgilang."))
        else:
            question = QuizQuestion.objects.create(
                quiz=quiz, text=text, order=quiz.questions.count() + 1,
            )
            for i, choice_text in enumerate(choices, start=1):
                QuizChoice.objects.create(
                    question=question, text=choice_text,
                    is_correct=(str(i) == correct_index), order=i,
                )
            messages.success(request, _("Savol qo'shildi."))
        return redirect("panel:quiz_manage", course_pk=course_pk, pk=pk)

    return render(request, "panel/courses/quiz_manage.html", {
        "page_title": _("Dars testi") + f" — {lesson.title}",
        "course": lesson.module.course, "lesson": lesson, "quiz": quiz, "form": form,
        "questions": quiz.questions.prefetch_related("choices").order_by("order", "id"),
    })


@staff_required
@require_POST
def quiz_question_delete(request, course_pk, pk, question_pk):
    question = get_object_or_404(QuizQuestion, pk=question_pk, quiz__lesson_id=pk)
    question.delete()
    messages.success(request, _("Savol o'chirildi."))
    return redirect("panel:quiz_manage", course_pk=course_pk, pk=pk)


@staff_required
def lesson_list(request):
    """Barcha darslar — kurslar bo'yicha filtr bilan."""
    qs = Lesson.objects.select_related("module", "module__course").order_by(
        "module__course__title", "module__order", "order"
    )
    course_id = request.GET.get("course") or ""
    search = (request.GET.get("q") or "").strip()
    if course_id:
        qs = qs.filter(module__course_id=course_id)
    if search:
        qs = qs.filter(title__icontains=search)
    return render(request, "panel/courses/lessons.html", {
        "page_title": _("Darslar"),
        "page": paginate(request, qs, 30),
        "courses": Course.objects.order_by("title"),
        "course_id": course_id, "search": search,
    })
